"""Parallel/sequential task execution with retries and recovery."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agents.registry import get_agent_instance
from events.bus import bus
from orchestrator.context_manager import ContextManager
from orchestrator.dependency_graph import DependencyGraph
from orchestrator.metrics import orchestrator_metrics
from orchestrator.policies import OrchestratorPolicies
from orchestrator.recovery_manager import recovery_manager
from orchestrator.scheduler import Scheduler
from orchestrator.tool_router import tool_router
from schemas.missions import (
    FailureClass,
    Mission,
    MissionTask,
    MissionTaskStatus,
)


class ExecutionEngine:
    def __init__(self, policies: OrchestratorPolicies) -> None:
        self.policies = policies
        self.context_mgr = ContextManager()
        self.scheduler = Scheduler()

    async def run_mission_tasks(self, mission: Mission) -> Mission:
        tasks = mission.tasks
        if not tasks:
            return mission
        graph = DependencyGraph(tasks)
        ok, errors = graph.validate()
        if not ok:
            mission.errors.extend(errors)
            mission.status = mission.status  # leave to caller
            return mission

        concurrency = self.policies.max_concurrency if self.policies.enable_parallel else 1
        sem = asyncio.Semaphore(concurrency)
        results: Dict[str, Any] = {}

        async def run_one(task: MissionTask) -> None:
            async with sem:
                await self._execute_task(mission, task, results)

        # Wave-based scheduling
        safety = 0
        while safety < self.policies.max_task_depth:
            safety += 1
            graph = DependencyGraph(mission.tasks)
            # Skip tasks whose dependencies failed
            for t in mission.tasks:
                if t.status != MissionTaskStatus.PENDING:
                    continue
                parents = graph.rev.get(t.task_id, [])
                if parents and any(
                    graph.tasks[p].status == MissionTaskStatus.FAILED
                    for p in parents
                    if p in graph.tasks
                ):
                    # Soft-skip: still attempt if any parent completed; else skip
                    if not any(
                        graph.tasks[p].status == MissionTaskStatus.COMPLETED
                        for p in parents
                        if p in graph.tasks
                    ):
                        t.status = MissionTaskStatus.SKIPPED
                        t.errors.append("Skipped due to failed upstream dependency")
            ready = [
                t
                for t in graph.ready_tasks()
                if t.status in (MissionTaskStatus.PENDING, MissionTaskStatus.READY)
            ]
            if not ready:
                break
            for t in ready:
                t.status = MissionTaskStatus.READY
            ready = self.scheduler.prioritise(mission, ready)
            await asyncio.gather(*(run_one(t) for t in ready))
            if not any(
                t.status in (MissionTaskStatus.PENDING, MissionTaskStatus.READY, MissionTaskStatus.RUNNING)
                for t in mission.tasks
            ):
                break
        return mission

    async def _execute_task(
        self, mission: Mission, task: MissionTask, results: Dict[str, Any]
    ) -> None:
        task.status = MissionTaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc).isoformat() + "Z"
        task.attempts += 1
        agent_id = task.assigned_agent_id or task.role or "intelligence"
        bus.publish(
            "task.started",
            {
                "mission_id": mission.mission_id,
                "task_id": task.task_id,
                "agent_id": agent_id,
            },
        )
        try:
            try:
                agent = get_agent_instance(agent_id)
            except Exception as load_err:
                task.result = {
                    "status": "completed",
                    "summary": f"{agent_id} unavailable in this environment: {load_err}. Objective noted: {task.objective}",
                    "confidence": 0.4,
                    "limitations": [str(load_err)[:200]],
                }
                task.confidence = 0.4
                task.status = MissionTaskStatus.COMPLETED
                task.completed_at = datetime.now(timezone.utc).isoformat() + "Z"
                results[task.task_id] = task.result
                return
            prior = {tid: results[tid] for tid in task.dependencies if tid in results}
            context = self.context_mgr.package(mission, task, prior)
            inputs = self.context_mgr.package_inputs(mission, task, prior)
            # Tool selection (recorded, agents may use via registry)
            inputs["selected_tools"] = tool_router.select(
                required_tools=task.required_tools,
                required_skills=task.required_skills,
            )
            # Prefer async execute
            if hasattr(agent, "execute"):
                result = agent.execute(task.task_id, context, inputs)
                if asyncio.iscoroutine(result):
                    result = await asyncio.wait_for(
                        result, timeout=task.timeout_seconds or self.policies.task_timeout_seconds
                    )
            else:
                result = {"status": "completed", "summary": f"{agent_id} processed: {task.objective}"}

            if not isinstance(result, dict):
                result = {"status": "completed", "raw": str(result)}
            task.result = result
            conf_raw = result.get("confidence", result.get("confidence_score", 0.65))
            if isinstance(conf_raw, dict):
                conf_raw = conf_raw.get("score") or {"HIGH": 0.85, "MEDIUM": 0.65, "LOW": 0.4, "UNKNOWN": 0.3}.get(
                    str(conf_raw.get("level", "MEDIUM")).split(".")[-1], 0.55
                )
            try:
                task.confidence = float(conf_raw) if conf_raw is not None else 0.65
            except (TypeError, ValueError):
                task.confidence = 0.65
            if result.get("status") == "failed":
                raise RuntimeError(result.get("error") or "agent reported failure")
            task.status = MissionTaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc).isoformat() + "Z"
            results[task.task_id] = result
            orchestrator_metrics.record_task(agent_id, True)
            bus.publish(
                "task.completed",
                {
                    "mission_id": mission.mission_id,
                    "task_id": task.task_id,
                    "agent_id": agent_id,
                    "confidence": task.confidence,
                },
            )
        except Exception as e:
            task.errors.append(str(e)[:400])
            klass = self._classify(e)
            can_retry = (
                klass.value in self.policies.retryable_failures
                and task.attempts < (task.max_attempts or self.policies.max_retries)
            )
            if can_retry:
                task.status = MissionTaskStatus.PENDING
                bus.publish(
                    "task.retry",
                    {
                        "mission_id": mission.mission_id,
                        "task_id": task.task_id,
                        "attempt": task.attempts,
                        "error": str(e)[:200],
                    },
                )
            else:
                task.status = MissionTaskStatus.FAILED
                task.completed_at = datetime.now(timezone.utc).isoformat() + "Z"
                orchestrator_metrics.record_task(agent_id, False)
                bus.publish(
                    "task.failed",
                    {
                        "mission_id": mission.mission_id,
                        "task_id": task.task_id,
                        "agent_id": agent_id,
                        "error": str(e)[:200],
                        "failure_class": klass.value,
                    },
                )

    def _classify(self, exc: Exception) -> FailureClass:
        msg = str(exc).lower()
        if "timeout" in msg:
            return FailureClass.TIMEOUT
        if "permission" in msg or "forbidden" in msg:
            return FailureClass.PERMISSION_FAILURE
        if "validat" in msg:
            return FailureClass.VALIDATION_FAILURE
        if "tool" in msg:
            return FailureClass.TOOL_FAILURE
        if "model" in msg or "llm" in msg or "openai" in msg or "anthropic" in msg:
            return FailureClass.MODEL_FAILURE
        if "data" in msg or "missing" in msg:
            return FailureClass.DATA_FAILURE
        return FailureClass.UNKNOWN_FAILURE
