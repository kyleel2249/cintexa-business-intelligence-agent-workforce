"""Adaptive replanning — preserve completed work, extend plan with reason."""

from __future__ import annotations

from typing import List, Optional

from orchestrator.task_decomposer import TaskDecomposer
from schemas.missions import Mission, MissionPlan, MissionTask, MissionTaskStatus, OrchestrationDecision


class Replanner:
    def __init__(self) -> None:
        self.decomposer = TaskDecomposer()

    def should_replan(self, mission: Mission) -> tuple[bool, str]:
        failed = [t for t in mission.tasks if t.status == MissionTaskStatus.FAILED]
        if len(failed) >= 2:
            return True, "multiple_task_failures"
        if mission.conflicts and any(
            c.resolution_status.value == "UNRESOLVED" for c in mission.conflicts
        ):
            return True, "unresolved_conflicts"
        if mission.confidence < 0.45 and mission.status.value == "VERIFYING":
            return True, "low_confidence"
        return False, ""

    def build_extension(
        self, mission: Mission, reason: str, extra_analysis: Optional[List[str]] = None
    ) -> MissionPlan:
        completed = [t for t in mission.tasks if t.status == MissionTaskStatus.COMPLETED]
        if mission.intent and mission.normalized_objective:
            obj = mission.normalized_objective
            if extra_analysis:
                obj.analysis_requirements = list(
                    dict.fromkeys(list(obj.analysis_requirements) + extra_analysis)
                )
            new_tasks = self.decomposer.decompose(obj, mission.intent)
            # Drop tasks whose objective already completed
            done_objectives = {t.objective for t in completed}
            fresh = [t for t in new_tasks if t.objective not in done_objectives]
            tasks = completed + fresh
        else:
            tasks = list(mission.tasks)

        plan = MissionPlan(
            version=(mission.plan_version or 0) + 1,
            tasks=tasks,
            change_reason=reason,
            rationale=f"Replan: {reason}",
            team=list({(t.assigned_agent_id or t.role) for t in tasks if (t.assigned_agent_id or t.role)}),
        )
        return plan


replanner = Replanner()
