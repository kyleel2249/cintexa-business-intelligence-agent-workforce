"""Human approval gates for high-risk operations."""

from __future__ import annotations

from typing import List, Set

from orchestrator.policies import DEFAULT_POLICIES
from schemas.missions import Mission, MissionStatus, OrchestrationDecision


class ApprovalManager:
    def __init__(self) -> None:
        self.policies = DEFAULT_POLICIES

    def requires_approval(self, mission: Mission) -> bool:
        if not self.policies.enable_human_approval:
            return False
        triggers: Set[str] = set(mission.approval_requirements or [])
        if triggers & self.policies.approval_triggers:
            return True
        if mission.risk_level in ("high", "critical"):
            return True
        text = (mission.original_request or "").lower()
        for phrase in ("wire money", "send email to customers", "deploy to production", "sign contract"):
            if phrase in text:
                return True
        return False

    def request(self, mission: Mission) -> Mission:
        mission.status = MissionStatus.AWAITING_APPROVAL
        mission.decisions.append(
            OrchestrationDecision(
                mission_id=mission.mission_id,
                decision_type="approval_request",
                decision="awaiting_human_approval",
                reason="High-risk or policy-triggered operation",
                selected_option="AWAITING_APPROVAL",
            )
        )
        return mission


approval_manager = ApprovalManager()
