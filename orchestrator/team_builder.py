"""Assemble temporary specialist teams for a mission."""

from __future__ import annotations

from typing import List

from schemas.missions import MissionPlan, MissionTask


class TeamBuilder:
    def assemble(self, tasks: List[MissionTask]) -> List[str]:
        team = []
        for t in tasks:
            aid = t.assigned_agent_id or t.role
            if aid and aid not in team:
                team.append(aid)
        if "quality" not in team:
            team.append("quality")
        return team

    def apply(self, plan: MissionPlan) -> MissionPlan:
        plan.team = self.assemble(plan.tasks)
        return plan
