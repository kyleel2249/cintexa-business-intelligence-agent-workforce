"""Orchestration decision log."""

from __future__ import annotations

from typing import List, Optional

from schemas.missions import Mission, OrchestrationDecision


class DecisionLogger:
    def log(self, mission: Mission, decision: OrchestrationDecision) -> None:
        mission.decisions.append(decision)
        mission.events.append(
            {
                "event_type": "orchestration.decision",
                "mission_id": mission.mission_id,
                "decision_type": decision.decision_type,
                "decision": decision.decision,
                "timestamp": decision.timestamp,
            }
        )

    def explain(self, mission: Mission, decision_type: Optional[str] = None) -> List[OrchestrationDecision]:
        if not decision_type:
            return list(mission.decisions)
        return [d for d in mission.decisions if d.decision_type == decision_type]
