"""Governed external write actions with idempotency and verification."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional, Set

from core.errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from events.bus import bus
from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from external_fabric.governor import InteractionGovernor
from external_fabric.models_db import ExtAction, ExtApproval
from external_fabric.providers.mock import MockBrowserProvider


class ExternalActionService:
    def __init__(self, provider=None):
        self.provider = provider or MockBrowserProvider()
        self.governor = InteractionGovernor()

    def request(
        self,
        organisation_id: str,
        capability_id: str,
        *,
        target: str = "",
        content: str = "",
        agent_id: str = "",
        account_id: str = "",
        permissions: Optional[Set[str]] = None,
        idempotency_key: Optional[str] = None,
        budget_remaining: Optional[int] = None,
    ) -> dict:
        if idempotency_key:
            with UnitOfWork() as uow:
                existing = (
                    uow.session.query(ExtAction)
                    .filter_by(organisation_id=organisation_id, idempotency_key=idempotency_key)
                    .first()
                )
                if existing:
                    return {
                        "action_id": existing.action_id,
                        "status": existing.status,
                        "deduped": True,
                        "result": existing.result,
                    }

        decision = self.governor.evaluate(
            organisation_id=organisation_id,
            capability_id=capability_id,
            target=target,
            content=content,
            agent_id=agent_id,
            account_id=account_id,
            permissions=permissions or set(),
            budget_remaining=budget_remaining,
        )
        aid = new_id("EA-")
        ch = hashlib.sha256((content or "").encode()).hexdigest()[:32] if content else None
        with UnitOfWork() as uow:
            uow.session.add(
                ExtAction(
                    action_id=aid,
                    organisation_id=organisation_id,
                    capability_id=capability_id,
                    target=target,
                    content_hash=ch,
                    idempotency_key=idempotency_key,
                    status="BLOCKED" if decision.decision in ("BLOCK", "REJECT") else (
                        "PENDING_APPROVAL" if decision.decision == "REQUIRE_APPROVAL" else "APPROVED"
                    ),
                    decision=decision.decision,
                    decision_reason=decision.reason,
                )
            )
            if decision.decision == "REQUIRE_APPROVAL":
                uow.session.add(
                    ExtApproval(
                        approval_id=new_id("EAP-"),
                        organisation_id=organisation_id,
                        action_id=aid,
                        capability_id=capability_id,
                        target=target,
                        content=content[:4000],
                        risk=decision.risk,
                        status="PENDING",
                        reason=decision.reason,
                    )
                )

        if decision.decision in ("BLOCK", "REJECT", "DEFER"):
            bus.publish(
                "external.action.blocked",
                {"action_id": aid, "reason": decision.reason},
                organisation_id=organisation_id,
            )
            return {
                "action_id": aid,
                "status": decision.decision,
                "reason": decision.reason,
                "risk": decision.risk,
            }

        if decision.decision == "REQUIRE_APPROVAL":
            bus.publish(
                "external.action.approval_required",
                {"action_id": aid},
                organisation_id=organisation_id,
            )
            return {"action_id": aid, "status": "PENDING_APPROVAL", "reason": decision.reason}

        return self._execute(organisation_id, aid, capability_id, target, content, agent_id, account_id)

    def approve(self, organisation_id: str, action_id: str, *, approver: str) -> dict:
        with UnitOfWork() as uow:
            action = uow.session.get(ExtAction, action_id)
            if not action or action.organisation_id != organisation_id:
                raise NotFoundError("Action not found")
            if action.status != "PENDING_APPROVAL":
                raise ValidationError(f"Cannot approve status {action.status}")
            appr = (
                uow.session.query(ExtApproval)
                .filter_by(action_id=action_id, organisation_id=organisation_id, status="PENDING")
                .first()
            )
            content = appr.content if appr else ""
            target = action.target
            capability_id = action.capability_id
            if appr:
                appr.status = "APPROVED"
                appr.decided_by = approver
                appr.decided_at = datetime.utcnow()
            action.status = "APPROVED"
        return self._execute(organisation_id, action_id, capability_id, target, content, "", "")

    def _execute(
        self,
        organisation_id: str,
        action_id: str,
        capability_id: str,
        target: str,
        content: str,
        agent_id: str,
        account_id: str,
    ) -> dict:
        # kill switch re-check
        if self.governor.kill.writes_blocked(organisation_id) and capability_id not in (
            "WEB_OPEN_URL",
            "WEB_READ_PAGE",
            "SOCIAL_READ",
            "MEDIA_VIEW",
        ):
            return {"action_id": action_id, "status": "BLOCK", "reason": "EXTERNAL_WRITE_KILL_SWITCH"}

        result = {"status": "FAILED"}
        verification = "UNKNOWN"
        if capability_id == "SOCIAL_LIKE":
            result = self.provider.like(target)
            verification = "SUCCESS" if result.get("liked") else "FAILED"
        elif capability_id in ("SOCIAL_COMMENT", "SOCIAL_REPLY"):
            result = self.provider.comment(target, content)
            verification = "SUCCESS" if result.get("comment_id") else "FAILED"
        else:
            result = {"status": "SUCCESS", "note": "no-op mock execute"}
            verification = "SUCCESS"

        self.governor.record_action(
            organisation_id=organisation_id,
            capability_id=capability_id,
            target=target,
            content=content,
            agent_id=agent_id,
            account_id=account_id,
        )
        with UnitOfWork() as uow:
            action = uow.session.get(ExtAction, action_id)
            if action and action.organisation_id == organisation_id:
                action.status = "COMPLETED" if verification == "SUCCESS" else "FAILED"
                action.result = result
                action.verification = verification
                action.completed_at = datetime.utcnow()
        bus.publish(
            "external.action.completed",
            {"action_id": action_id, "verification": verification},
            organisation_id=organisation_id,
        )
        return {
            "action_id": action_id,
            "status": "COMPLETED" if verification == "SUCCESS" else "FAILED",
            "result": result,
            "verification": verification,
        }
