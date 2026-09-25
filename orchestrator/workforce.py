"""
CINTEXA Workforce Intelligence & Execution Orchestrator.

Mission pipeline:
  understand → normalize → decompose → DAG → select agents → team →
  schedule/execute → evaluate → conflicts → quality → synthesise → deliver
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from events.bus import bus
from orchestrator.agent_router import AgentRouter
from orchestrator.conflict_manager import ConflictManager
from orchestrator.decision_logger import DecisionLogger
from orchestrator.dependency_graph import DependencyGraph
from orchestrator.evidence_gate import EvidenceGate
from orchestrator.execution_engine import ExecutionEngine
from orchestrator.hypothesis_manager import HypothesisManager
from orchestrator.intent_engine import IntentEngine
from orchestrator.mission_manager import mission_manager
from orchestrator.objective_normalizer import ObjectiveNormalizer
from orchestrator.policies import DEFAULT_POLICIES, OrchestratorPolicies
from orchestrator.stopping_engine import StoppingEngine
from orchestrator.synthesis_engine import SynthesisEngine
from orchestrator.task_decomposer import TaskDecomposer
from orchestrator.team_builder import TeamBuilder
from schemas.missions import (
    AmbiguityLevel,
    Mission,
    MissionCreate,
    MissionPlan,
    MissionPriority,
    MissionResult,
    MissionStatus,
    MissionTaskStatus,
    OrchestrationDecision,
)


class WorkforceOrchestrator:
    """Central coordination layer for the CINTEXA agent workforce."""

    def __init__(self, policies: Optional[OrchestratorPolicies] = None) -> None:
        self.policies = policies or DEFAULT_POLICIES
        self.intent_engine = IntentEngine()
        self.normalizer = ObjectiveNormalizer()
        self.decomposer = TaskDecomposer()
        self.router = AgentRouter()
        self.team_builder = TeamBuilder()
        self.execution = ExecutionEngine(self.policies)
        self.evidence_gate = EvidenceGate()
        self.conflicts = ConflictManager()
        self.hypotheses = HypothesisManager()
        self.stopping = StoppingEngine()
        self.synthesis = SynthesisEngine()
        self.decisions = DecisionLogger()
        self.store = mission_manager

    # ── public API ──────────────────────────────────────────────

    async def create_and_run(
        self,
        payload: MissionCreate,
        *,
        api_key: Optional[str] = None,
        auto_run: bool = True,
    ) -> Mission:
        if payload.idempotency_key:
            existing = self.store.get_by_idempotency(
                payload.organisation_id, payload.idempotency_key
            )
            if existing:
                return existing

        mission = Mission(
            organisation_id=payload.organisation_id,
            workspace_id=payload.workspace_id,
            user_id=payload.user_id,
            objective=payload.objective,
            original_request=payload.objective,
            priority=payload.priority,
            constraints=list(payload.constraints),
            success_criteria=list(payload.success_criteria),
            required_outputs=list(payload.required_outputs),
            available_context=dict(payload.context or {}),
            deadline=payload.deadline,
            approval_requirements=list(payload.approval_requirements),
            idempotency_key=payload.idempotency_key,
            status=MissionStatus.CREATED,
        )
        self.store.save(mission)
        self._emit(mission, "mission.created")
        mission = await self._understand_and_plan(mission, api_key=api_key)
        if auto_run and mission.status in (
            MissionStatus.READY,
            MissionStatus.PLANNING,
            MissionStatus.RUNNING,
        ):
            mission = await self.run(mission.mission_id, api_key=api_key)
        return self.store.get(mission.mission_id) or mission

    async def run(self, mission_id: str, *, api_key: Optional[str] = None) -> Mission:
        mission = self.store.get(mission_id)
        if not mission:
            raise KeyError(f"Mission {mission_id} not found")
        if mission.status in (MissionStatus.CANCELLED, MissionStatus.COMPLETED):
            return mission
        if mission.status == MissionStatus.AWAITING_APPROVAL:
            return mission
        if mission.status == MissionStatus.PAUSED:
            return mission

        mission.status = MissionStatus.RUNNING
        mission.started_at = mission.started_at or (
            datetime.now(timezone.utc).isoformat() + "Z"
        )
        self.store.save(mission)
        self._emit(mission, "mission.started")

        # Approval gate
        if mission.approval_requirements and self.policies.enable_human_approval:
            risky = set(mission.approval_requirements) & self.policies.approval_triggers
            if risky:
                mission.status = MissionStatus.AWAITING_APPROVAL
                self.decisions.log(
                    mission,
                    OrchestrationDecision(
                        mission_id=mission.mission_id,
                        decision_type="approval_request",
                        decision="pause_for_approval",
                        reason=f"Triggers: {sorted(risky)}",
                        selected_option="AWAITING_APPROVAL",
                    ),
                )
                self.store.save(mission)
                self._emit(mission, "approval.requested")
                return mission

        mission = await self.execution.run_mission_tasks(mission)

        # Collect results for conflict detection
        results_map = {
            (t.assigned_agent_id or t.role or t.task_id): t.result
            for t in mission.tasks
            if t.status == MissionTaskStatus.COMPLETED and isinstance(t.result, dict)
        }
        detected = self.conflicts.detect(results_map)
        for c in detected:
            resolved = self.conflicts.resolve(c)
            mission.conflicts.append(resolved)
            self._emit(mission, "conflict.detected", {"conflict_id": resolved.conflict_id})

        # Evidence / confidence
        flat_evidence = list(mission.evidence)
        for t in mission.tasks:
            if t.status == MissionTaskStatus.COMPLETED and t.confidence:
                flat_evidence.append(
                    {"task_id": t.task_id, "confidence": t.confidence, "source": "task_result"}
                )
        sufficiency = self.evidence_gate.evaluate(flat_evidence, mission.risk_level)
        confs = [t.confidence for t in mission.tasks if t.status == MissionTaskStatus.COMPLETED]
        mission.confidence = sum(confs) / len(confs) if confs else 0.4
        mission.execution_metrics = {
            "tasks_total": len(mission.tasks),
            "tasks_completed": sum(
                1 for t in mission.tasks if t.status == MissionTaskStatus.COMPLETED
            ),
            "tasks_failed": sum(1 for t in mission.tasks if t.status == MissionTaskStatus.FAILED),
            "evidence_sufficiency": sufficiency.value,
            "conflicts": len(mission.conflicts),
        }

        stop, reason = self.stopping.should_stop(mission, self.policies)
        self.decisions.log(
            mission,
            OrchestrationDecision(
                mission_id=mission.mission_id,
                decision_type="stopping",
                decision="stop" if stop else "continue",
                reason=reason,
                selected_option=reason,
                confidence=mission.confidence,
            ),
        )

        mission.status = MissionStatus.VERIFYING
        result = self.synthesis.synthesise(mission, api_key=api_key)
        mission.result = result
        mission.quality_score = result.quality
        mission.confidence = result.confidence
        mission.status = MissionStatus.COMPLETED
        mission.completed_at = datetime.now(timezone.utc).isoformat() + "Z"
        self.store.save(mission)
        self._emit(mission, "mission.completed", {"confidence": mission.confidence})
        return mission

    async def cancel(self, mission_id: str) -> Mission:
        mission = self._require(mission_id)
        mission.status = MissionStatus.CANCELLED
        for t in mission.tasks:
            if t.status in (
                MissionTaskStatus.PENDING,
                MissionTaskStatus.READY,
                MissionTaskStatus.RUNNING,
            ):
                t.status = MissionTaskStatus.CANCELLED
        self.store.save(mission)
        self._emit(mission, "mission.cancelled")
        return mission

    async def pause(self, mission_id: str) -> Mission:
        mission = self._require(mission_id)
        mission.status = MissionStatus.PAUSED
        self.store.save(mission)
        self._emit(mission, "mission.paused")
        return mission

    async def resume(self, mission_id: str, *, api_key: Optional[str] = None) -> Mission:
        mission = self._require(mission_id)
        if mission.status not in (
            MissionStatus.PAUSED,
            MissionStatus.AWAITING_APPROVAL,
            MissionStatus.BLOCKED,
        ):
            return mission
        mission.status = MissionStatus.READY
        self.store.save(mission)
        self._emit(mission, "mission.resumed")
        return await self.run(mission_id, api_key=api_key)

    async def approve(self, mission_id: str, *, api_key: Optional[str] = None) -> Mission:
        mission = self._require(mission_id)
        if mission.status != MissionStatus.AWAITING_APPROVAL:
            return mission
        self.decisions.log(
            mission,
            OrchestrationDecision(
                mission_id=mission.mission_id,
                decision_type="approval_granted",
                decision="approved",
                reason="User/system approval received",
            ),
        )
        self._emit(mission, "approval.granted")
        mission.status = MissionStatus.READY
        self.store.save(mission)
        return await self.run(mission_id, api_key=api_key)

    async def replan(
        self, mission_id: str, reason: str = "manual_replan", *, api_key: Optional[str] = None
    ) -> Mission:
        mission = self._require(mission_id)
        mission.status = MissionStatus.REPLANNING
        if mission.plan:
            mission.plan_history.append(mission.plan)
        # Keep completed task outputs; rebuild only incomplete work
        completed = [t for t in mission.tasks if t.status == MissionTaskStatus.COMPLETED]
        mission = await self._understand_and_plan(mission, api_key=api_key, preserve=completed)
        self.decisions.log(
            mission,
            OrchestrationDecision(
                mission_id=mission.mission_id,
                decision_type="replan",
                decision=f"plan_v{mission.plan_version}",
                reason=reason,
            ),
        )
        self._emit(mission, "plan.changed", {"version": mission.plan_version, "reason": reason})
        return await self.run(mission_id, api_key=api_key)

    def get(self, mission_id: str) -> Optional[Mission]:
        return self.store.get(mission_id)

    def trace(self, mission_id: str) -> Dict[str, Any]:
        mission = self._require(mission_id)
        return {
            "mission_id": mission.mission_id,
            "status": mission.status.value,
            "plan_version": mission.plan_version,
            "team": mission.assigned_agents,
            "tasks": [
                {
                    "task_id": t.task_id,
                    "objective": t.objective,
                    "status": t.status.value,
                    "agent": t.assigned_agent_id or t.role,
                    "dependencies": t.dependencies,
                    "confidence": t.confidence,
                    "errors": t.errors,
                }
                for t in mission.tasks
            ],
            "conflicts": [c.model_dump() for c in mission.conflicts],
            "decisions": [d.model_dump() for d in mission.decisions],
            "events": mission.events[-100:],
            "execution_trace": mission.result.execution_trace if mission.result else "",
        }

    # ── internals ───────────────────────────────────────────────

    async def _understand_and_plan(
        self,
        mission: Mission,
        *,
        api_key: Optional[str] = None,
        preserve: Optional[List] = None,
    ) -> Mission:
        mission.status = MissionStatus.UNDERSTANDING
        self.store.save(mission)

        intent = self.intent_engine.understand(
            mission.original_request or mission.objective,
            context=mission.available_context,
            api_key=api_key,
        )
        mission.intent = intent
        mission.business_domain = intent.business_domain
        mission.missing_information = list(intent.missing_data)
        mission.priority = intent.priority

        if intent.ambiguity == AmbiguityLevel.CRITICAL and not mission.available_context:
            mission.status = MissionStatus.WAITING_FOR_INPUT
            self.decisions.log(
                mission,
                OrchestrationDecision(
                    mission_id=mission.mission_id,
                    decision_type="ambiguity",
                    decision="ask_user",
                    reason=f"Ambiguity={intent.ambiguity.value}",
                    selected_option="WAITING_FOR_INPUT",
                ),
            )
            self.store.save(mission)
            return mission

        mission.status = MissionStatus.PLANNING
        normalized = self.normalizer.normalize(intent, mission.original_request)
        mission.normalized_objective = normalized
        mission.objective = normalized.objective
        mission.success_criteria = list(normalized.success_criteria)

        tasks = self.decomposer.decompose(normalized, intent)
        # Agent selection
        for t in tasks:
            agent_id, decision = self.router.select(
                t, domain=intent.business_domain, mission_id=mission.mission_id
            )
            t.assigned_agent_id = agent_id
            self.decisions.log(mission, decision)

        # Merge preserved completed tasks
        if preserve:
            preserved_ids = {t.task_id for t in preserve}
            # keep preserved as-is, replace the rest
            new_tasks = list(preserve) + [t for t in tasks if t.task_id not in preserved_ids]
            tasks = new_tasks

        graph = DependencyGraph(tasks)
        ok, errors = graph.validate()
        if not ok:
            mission.errors.extend(errors)
            mission.status = MissionStatus.FAILED
            self.store.save(mission)
            return mission

        layers = graph.topological_layers()
        plan = MissionPlan(
            version=mission.plan_version + 1,
            tasks=tasks,
            parallel_groups=layers,
            team=[],
            rationale=f"Domain={intent.business_domain}; analysis={normalized.analysis_requirements}",
        )
        plan = self.team_builder.apply(plan)
        mission.plan = plan
        mission.plan_version = plan.version
        mission.tasks = tasks
        mission.assigned_agents = list(plan.team)
        mission.hypotheses = self.hypotheses.seed_from_objective(mission)
        mission.status = MissionStatus.READY
        self.store.save(mission)
        self._emit(
            mission,
            "mission.planned",
            {"version": plan.version, "tasks": len(tasks), "team": plan.team},
        )
        return mission

    def _require(self, mission_id: str) -> Mission:
        m = self.store.get(mission_id)
        if not m:
            raise KeyError(f"Mission {mission_id} not found")
        return m

    def _emit(self, mission: Mission, event_type: str, payload: Optional[Dict] = None) -> None:
        event = {
            "event_type": event_type,
            "mission_id": mission.mission_id,
            "organisation_id": mission.organisation_id,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "payload": payload or {},
        }
        mission.events.append(event)
        try:
            bus.publish(event_type, event, mission.organisation_id)
        except TypeError:
            bus.publish(event_type, event)


# Singleton used by API layer
workforce = WorkforceOrchestrator()
