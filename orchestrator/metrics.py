"""Orchestrator metrics for learning and observability."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict


class OrchestratorMetrics:
    def __init__(self) -> None:
        self.missions_total = 0
        self.missions_completed = 0
        self.missions_failed = 0
        self.tasks_total = 0
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.retries = 0
        self.fallbacks = 0
        self.conflicts = 0
        self.replans = 0
        self.approvals = 0
        self.agent_success: Dict[str, int] = defaultdict(int)
        self.agent_failure: Dict[str, int] = defaultdict(int)
        self.durations: list = []

    def record_mission(self, status: str, duration_s: float = 0.0) -> None:
        self.missions_total += 1
        if status == "COMPLETED":
            self.missions_completed += 1
        elif status == "FAILED":
            self.missions_failed += 1
        if duration_s:
            self.durations.append(duration_s)

    def record_task(self, agent_id: str, success: bool) -> None:
        self.tasks_total += 1
        if success:
            self.tasks_completed += 1
            self.agent_success[agent_id] += 1
        else:
            self.tasks_failed += 1
            self.agent_failure[agent_id] += 1

    def snapshot(self) -> Dict[str, Any]:
        avg_dur = sum(self.durations) / len(self.durations) if self.durations else 0.0
        return {
            "mission_success_rate": (self.missions_completed / self.missions_total)
            if self.missions_total
            else 0.0,
            "task_success_rate": (self.tasks_completed / self.tasks_total) if self.tasks_total else 0.0,
            "average_mission_duration": avg_dur,
            "missions_total": self.missions_total,
            "tasks_total": self.tasks_total,
            "retries": self.retries,
            "fallbacks": self.fallbacks,
            "conflicts": self.conflicts,
            "replans": self.replans,
            "approvals": self.approvals,
            "agent_success": dict(self.agent_success),
            "agent_failure": dict(self.agent_failure),
        }


orchestrator_metrics = OrchestratorMetrics()
