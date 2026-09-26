"""Approval engine — no self-approval; hash-bound; invalidates on proposal change."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from core.errors import AuthorizationError, ValidationError
from events.bus import bus
from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from evolution.governance import (
    RiskLevel,
    change_freeze,
    default_policy,
    is_prohibited,
)
from evolution.models_db import EvoApproval, EvoProposal


class ApprovalEngine:
    def approve(
        self,
        organisation_id: str,
        proposal_id: str,
        *,
        approver: str,
        role: str = "human",
        reason: str = "",
        decision: str = "APPROVED",
        conditions: Optional[Dict] = None,
        expires_hours: Optional[int] = 72,
    ) -> Dict[str, Any]:
        if role == "system" or approver in ("self", "agent", "autonomous"):
            raise AuthorizationError("Self-approval is prohibited")
        if change_freeze.emergency_stop:
            raise AuthorizationError("Emergency stop — approvals blocked")

        with UnitOfWork() as uow:
            prop = uow.session.get(EvoProposal, proposal_id)
            if not prop or prop.organisation_id != organisation_id:
                from core.errors import NotFoundError
                raise NotFoundError("Proposal not found")
            if is_prohibited(prop.category) and decision == "APPROVED" and role != "security_admin":
                # LEVEL_4 prohibited categories need elevated role
                if prop.risk_level == RiskLevel.LEVEL_4.value:
                    raise AuthorizationError(
                        f"Category {prop.category} requires security_admin approval"
                    )
            aid = new_id("APR-")
            expires = datetime.utcnow() + timedelta(hours=expires_hours) if expires_hours else None
            uow.session.add(
                EvoApproval(
                    approval_id=aid,
                    organisation_id=organisation_id,
                    proposal_id=proposal_id,
                    proposal_hash=prop.content_hash,
                    approver=approver,
                    role=role,
                    decision=decision,
                    reason=reason,
                    risk_level=prop.risk_level,
                    conditions=conditions or {},
                    expires_at=expires,
                )
            )
            if decision in ("APPROVED", "APPROVED_WITH_CONDITIONS"):
                prop.status = "APPROVED"
            elif decision == "REJECTED":
                prop.status = "REJECTED"
        bus.publish(
            "evolution.approval.recorded",
            {"approval_id": aid, "proposal_id": proposal_id, "decision": decision},
            organisation_id=organisation_id,
        )
        return {"approval_id": aid, "decision": decision, "proposal_hash": prop.content_hash if prop else None}

    def get_valid_approval(self, organisation_id: str, proposal_id: str) -> Optional[Dict]:
        with UnitOfWork() as uow:
            prop = uow.session.get(EvoProposal, proposal_id)
            if not prop or prop.organisation_id != organisation_id:
                return None
            rows = (
                uow.session.query(EvoApproval)
                .filter_by(organisation_id=organisation_id, proposal_id=proposal_id)
                .order_by(EvoApproval.created_at.desc())
                .all()
            )
            for r in rows:
                if r.decision not in ("APPROVED", "APPROVED_WITH_CONDITIONS"):
                    continue
                if r.proposal_hash != prop.content_hash:
                    continue  # invalidated by modification
                if r.expires_at and r.expires_at < datetime.utcnow():
                    continue
                return {
                    "approval_id": r.approval_id,
                    "approver": r.approver,
                    "decision": r.decision,
                    "proposal_hash": r.proposal_hash,
                }
            return None

    def auto_approve_if_allowed(self, organisation_id: str, proposal_id: str) -> Optional[Dict]:
        with UnitOfWork() as uow:
            prop = uow.session.get(EvoProposal, proposal_id)
            if not prop or prop.organisation_id != organisation_id:
                return None
            risk = RiskLevel(prop.risk_level)
            if not default_policy.may_auto_approve(risk, prop.category):
                return None
        return self.approve(
            organisation_id,
            proposal_id,
            approver="policy:auto",
            role="policy",
            reason="Low-risk auto-approval under governance policy",
            decision="APPROVED",
        )
