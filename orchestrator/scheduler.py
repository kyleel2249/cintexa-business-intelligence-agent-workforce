"""Priority-aware task scheduler helpers."""

from __future__ import annotations

from typing import List

from orchestrator.dependency_graph import DependencyGraph
from schemas.missions import Mission, MissionTask, MissionTaskStatus


class Scheduler:
    def prioritise(self, mission: Mission, ready: List[MissionTask]) -> List[MissionTask]:
        graph = DependencyGraph(mission.tasks)
        # priority score = base priority + blocking potential + mission urgency boost
        urgency_boost = {
            "LOW": 0.0,
            "NORMAL": 0.05,
            "HIGH": 0.15,
            "URGENT": 0.25,
            "CRITICAL": 0.35,
        }.get(getattr(mission.priority, "value", str(mission.priority)), 0.05)

        def score(t: MissionTask) -> float:
            block = graph.blocking_score(t.task_id) * 0.05
            return float(t.priority) + block + urgency_boost

        return sorted(ready, key=score, reverse=True)

    def estimate_critical_path(self, mission: Mission) -> int:
        return DependencyGraph(mission.tasks).critical_path_length()
