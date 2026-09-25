"""Agent + role selection with transparent scoring."""

from __future__ import annotations

from typing import List, Optional, Tuple

from orchestrator.capability_registry import capability_registry
from schemas.missions import MissionTask, OrchestrationDecision


class AgentRouter:
    def select(
        self,
        task: MissionTask,
        *,
        domain: Optional[str] = None,
        mission_id: str = "",
        exclude: Optional[List[str]] = None,
    ) -> Tuple[Optional[str], OrchestrationDecision]:
        # Prefer explicit role hint from decomposer
        preferred = task.role
        ranked = capability_registry.rank(
            required_skills=task.required_skills or task.required_capabilities,
            domain=domain,
            required_tools=task.required_tools,
            exclude=exclude,
            top_k=6,
        )
        selected = None
        options = [f"{aid}:{score:.2f}" for aid, score, _ in ranked]
        if preferred and any(aid == preferred for aid, _, _ in ranked):
            selected = preferred
        elif preferred and capability_registry.get(preferred):
            selected = preferred
        elif ranked:
            selected = ranked[0][0]

        decision = OrchestrationDecision(
            mission_id=mission_id,
            decision_type="agent_selection",
            decision=f"Assign {selected} to task {task.task_id}",
            reason=f"skills={task.required_skills} domain={domain} preferred={preferred}",
            available_options=options,
            selected_option=selected or "",
            confidence=ranked[0][1] if ranked else 0.3,
        )
        return selected, decision
