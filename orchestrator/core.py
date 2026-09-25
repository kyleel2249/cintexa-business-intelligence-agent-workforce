"""CINTEXA BI Orchestrator — manager of the Business Intelligence workforce."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agents.registry import get_agent, list_agents
from events.bus import bus
from orchestrator.planner import build_task_plan
from schemas.common import TaskState
from schemas.tasks import Task, TaskCreate, TaskPlan

# agent_id -> event-name prefix, for lifecycle events published on the shared bus.
# Agents without a dedicated prefix here simply don't get .started/.completed events,
# but every agent still gets "agent.failed" on exception.
_AGENT_EVENT_PREFIX = {
    "diagnostic": "diagnostic",
    "research": "research",
    "competitor": "competitor.research",
    "quality": "qa",
}


class Orchestrator:
    """
    Understands the user request, creates a TaskPlan, selects specialists,
    maintains task state, monitors execution, routes through QA and synthesises
    the final response. Does not perform specialist work when a specialist is better suited.
    """

    agent_id = "orchestrator"

    def __init__(self):
        self.profile = get_agent("orchestrator")
        self._tasks: Dict[str, Task] = {}
        self._agent_instances: Dict[str, Any] = {}

    def register_agent_instance(self, agent_id: str, instance: Any) -> None:
        self._agent_instances[agent_id] = instance

    def create_task(self, payload: TaskCreate) -> Task:
        plan = build_task_plan(payload.request, payload.priority)
        task = Task(
            request=payload.request,
            objective=plan.objective,
            organisation_id=payload.organisation_id,
            user_id=payload.user_id,
            priority=payload.priority,
            state=TaskState.PLANNING,
            plan=plan,
            agents_assigned=plan.agents_required,
            context=payload.context,
            requires_human_approval=plan.requires_human_approval,
        )
        self._tasks[task.task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def update_state(self, task_id: str, state: TaskState, **kwargs) -> Task:
        task = self._tasks[task_id]
        task.state = state
        task.updated_at = datetime.now(timezone.utc)
        for k, v in kwargs.items():
            if hasattr(task, k):
                setattr(task, k, v)
        if state == TaskState.COMPLETED:
            task.completed_at = datetime.now(timezone.utc)
        return task

    async def run(self, task_id: str) -> Task:
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        if not task.plan:
            task.plan = build_task_plan(task.request, task.priority)

        self.update_state(task_id, TaskState.RUNNING)

        # Execute parallel groups first
        for group in task.plan.parallel_groups:
            results = await self._run_parallel(task, group)
            for agent_id, result in results.items():
                task.results[agent_id] = result
                if isinstance(result, dict) and result.get("evidence_ids"):
                    task.evidence_ids.extend(result["evidence_ids"])

        # Sequential steps
        for agent_id in task.plan.sequential_steps:
            if agent_id in task.results:
                continue  # already ran in parallel
            # Check dependencies
            deps = task.plan.dependencies.get(agent_id, [])
            for d in deps:
                if d not in task.results:
                    self.update_state(task_id, TaskState.WAITING_FOR_AGENT)
                    # In production this would park the task; for now continue when possible
            result = await self._run_agent(task, agent_id)
            task.results[agent_id] = result
            if isinstance(result, dict) and result.get("evidence_ids"):
                task.evidence_ids.extend(result["evidence_ids"])

        # Synthesis
        synthesised = self._synthesise(task)
        task.results["synthesis"] = synthesised

        # QA is last sequential step if present; otherwise run it
        if "quality" not in task.results:
            qa_result = await self._run_agent(task, "quality")
            task.results["quality"] = qa_result

        qa = task.results.get("quality", {})
        if qa.get("qa_result") == "REVISION_REQUIRED":
            self.update_state(task_id, TaskState.FAILED, errors=qa.get("reasons", []))
        else:
            self.update_state(task_id, TaskState.COMPLETED)

        return task

    async def _run_parallel(self, task: Task, agent_ids: List[str]) -> Dict[str, Any]:
        import asyncio

        coros = [self._run_agent(task, aid) for aid in agent_ids]
        outcomes = await asyncio.gather(*coros, return_exceptions=True)
        results = {}
        for aid, outcome in zip(agent_ids, outcomes):
            if isinstance(outcome, Exception):
                results[aid] = {"status": "failed", "error": str(outcome)}
                task.errors.append(f"{aid}: {outcome}")
            else:
                results[aid] = outcome
        return results

    async def _run_agent(self, task: Task, agent_id: str) -> Dict[str, Any]:
        instance = self._agent_instances.get(agent_id)
        if instance is None:
            # Lazy import and instantiate
            instance = self._load_agent(agent_id)
            if instance:
                self._agent_instances[agent_id] = instance
        if instance is None:
            return {
                "status": "unavailable",
                "reason": f"Agent {agent_id} not implemented or disabled",
            }

        context = {
            "task_id": task.task_id,
            "organisation_id": task.organisation_id,
            "prior_results": {k: v for k, v in task.results.items()},
            "user_context": task.context,
            "plan": task.plan.model_dump() if task.plan else {},
        }
        inputs = {
            "request": task.request,
            "objective": task.objective,
            **task.context,
        }
        event_prefix = _AGENT_EVENT_PREFIX.get(agent_id)
        if event_prefix:
            bus.publish(f"{event_prefix}.started", {"task_id": task.task_id, "agent_id": agent_id}, task.organisation_id)
        try:
            result = await instance.execute(task.task_id, context, inputs)
            if event_prefix:
                bus.publish(f"{event_prefix}.completed", {"task_id": task.task_id, "agent_id": agent_id}, task.organisation_id)
            elif agent_id == "forecasting":
                bus.publish("forecast.created", {"task_id": task.task_id}, task.organisation_id)
            return result
        except Exception as exc:
            task.errors.append(f"{agent_id} failed: {exc}")
            bus.publish(
                "agent.failed",
                {"task_id": task.task_id, "agent_id": agent_id, "error": str(exc)},
                task.organisation_id,
            )
            return {"status": "failed", "error": str(exc)}

    def _load_agent(self, agent_id: str):
        """Lazy-load agent modules."""
        mapping = {
            "strategy": ("agents.strategy", "ExecutiveStrategyAgent"),
            "intelligence": ("agents.intelligence", "BusinessIntelligenceAgent"),
            "diagnostic": ("agents.diagnostic", "BusinessDiagnosticAgent"),
            "market": ("agents.market", "MarketIntelligenceAgent"),
            "competitor": ("agents.competitor", "CompetitorResearchAgent"),
            "research": ("agents.research", "ResearchAgent"),
            "decision": ("agents.decision", "DecisionSupportAgent"),
            "forecasting": ("agents.forecasting", "ForecastingAgent"),
            "knowledge": ("agents.knowledge", "KnowledgeManagerAgent"),
            "memory": ("agents.memory", "MemoryAgent"),
            "quality": ("agents.quality", "QualityAssuranceAgent"),
        }
        if agent_id not in mapping:
            return None
        module_path, class_name = mapping[agent_id]
        import importlib

        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        return cls()

    def _synthesise(self, task: Task) -> Dict[str, Any]:
        """Combine validated specialist outputs into a coherent structure."""
        sections = {
            "executive_summary": None,
            "objective": task.objective,
            "data_used": [],
            "methodology": [],
            "findings": {},
            "evidence_ids": list(set(task.evidence_ids)),
            "key_metrics": [],
            "risks": [],
            "opportunities": [],
            "assumptions": [],
            "uncertainties": [],
            "recommendations": [],
            "action_plan": [],
            "sources": [],
            "confidence": {},
        }

        for agent_id, result in task.results.items():
            if not isinstance(result, dict) or result.get("status") == "failed":
                continue
            if "findings" in result:
                sections["findings"][agent_id] = result["findings"]
            if "recommendations" in result:
                sections["recommendations"].extend(result.get("recommendations", []))
            if "risks" in result:
                sections["risks"].extend(result.get("risks", []))
            if "opportunities" in result:
                sections["opportunities"].extend(result.get("opportunities", []))
            if "assumptions" in result:
                sections["assumptions"].extend(result.get("assumptions", []))
            if "metrics" in result:
                sections["key_metrics"].extend(result.get("metrics", []))
            if "summary" in result and not sections["executive_summary"]:
                sections["executive_summary"] = result["summary"]

        if not sections["executive_summary"]:
            sections["executive_summary"] = (
                f"Analysis completed for objective '{task.objective}'. "
                f"Agents involved: {', '.join(task.agents_assigned)}. "
                "See findings and evidence for details."
            )

        return sections

    def cancel_task(self, task_id: str) -> Task:
        return self.update_state(task_id, TaskState.CANCELLED)

    def pause_task(self, task_id: str) -> Task:
        return self.update_state(task_id, TaskState.PAUSED)

    def resume_task(self, task_id: str) -> Task:
        return self.update_state(task_id, TaskState.RUNNING)
