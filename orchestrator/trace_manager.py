"""Inspectable execution traces."""

from __future__ import annotations

from typing import Any, Dict

from schemas.missions import Mission


class TraceManager:
    def build(self, mission: Mission) -> Dict[str, Any]:
        return {
            "mission_id": mission.mission_id,
            "objective": mission.objective,
            "status": mission.status.value,
            "plan_version": mission.plan_version,
            "team": mission.assigned_agents,
            "tree": {
                "plan": f"v{mission.plan_version}",
                "tasks": [
                    {
                        "id": t.task_id,
                        "objective": t.objective,
                        "status": t.status.value,
                        "agent": t.assigned_agent_id or t.role,
                        "dependencies": t.dependencies,
                        "confidence": t.confidence,
                    }
                    for t in mission.tasks
                ],
                "evidence_count": len(mission.evidence or []),
                "conflicts": [c.conflict_id for c in (mission.conflicts or [])],
                "decisions": len(mission.decisions or []),
            },
            "events": mission.events[-100:],
            "execution_trace": mission.result.execution_trace if mission.result else "",
        }

    def explain_decision(self, mission: Mission, decision_type: str) -> list:
        return [
            d.model_dump()
            for d in mission.decisions
            if d.decision_type == decision_type
        ]


trace_manager = TraceManager()
