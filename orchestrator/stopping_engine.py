"""Stopping criteria for missions."""

from __future__ import annotations

from typing import Tuple

from orchestrator.policies import OrchestratorPolicies
from schemas.missions import Mission, MissionStatus, MissionTaskStatus


class StoppingEngine:
    def should_stop(self, mission: Mission, policies: OrchestratorPolicies) -> Tuple[bool, str]:
        if mission.status in (
            MissionStatus.CANCELLED,
            MissionStatus.FAILED,
            MissionStatus.AWAITING_APPROVAL,
        ):
            return True, f"status={mission.status.value}"

        tasks = mission.tasks or (mission.plan.tasks if mission.plan else [])
        if not tasks:
            return True, "no_tasks"

        pending = [t for t in tasks if t.status in (MissionTaskStatus.PENDING, MissionTaskStatus.READY, MissionTaskStatus.RUNNING, MissionTaskStatus.BLOCKED)]
        failed = [t for t in tasks if t.status == MissionTaskStatus.FAILED]
        completed = [t for t in tasks if t.status == MissionTaskStatus.COMPLETED]

        if not pending and completed:
            if mission.confidence >= policies.min_final_confidence or len(completed) >= 1:
                return True, "required_outputs_completed"
            return True, "all_tasks_finished_low_confidence"

        # Optional tasks can be skipped if confidence already high and critical path done
        if mission.confidence >= 0.9 and len(pending) <= 1:
            return True, "confidence_stop"

        if failed and not pending and not completed:
            return True, "all_failed"

        return False, "continue"
