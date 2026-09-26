"""Staging, canary, promote, rollback."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from core.errors import AuthorizationError, ValidationError
from events.bus import bus
from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from evolution.approval import ApprovalEngine
from evolution.governance import change_freeze, is_prohibited
from evolution.models_db import EvoProposal, EvoRelease
from evolution.proposals import ProposalService


class DeploymentEngine:
    def stage(
        self,
        organisation_id: str,
        proposal_id: str,
        *,
        version: str,
        components: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        if change_freeze.frozen or change_freeze.emergency_stop:
            raise AuthorizationError("Change freeze active — staging blocked")
        approval = ApprovalEngine().get_valid_approval(organisation_id, proposal_id)
        if not approval:
            raise AuthorizationError("Valid approval required to stage")
        with UnitOfWork() as uow:
            prop = uow.session.get(EvoProposal, proposal_id)
            if not prop or prop.organisation_id != organisation_id:
                from core.errors import NotFoundError
                raise NotFoundError("Proposal not found")
            if is_prohibited(prop.category) and prop.risk_level == "LEVEL_4":
                # still needs approval which we checked
                pass
            rid = new_id("REL-")
            uow.session.add(
                EvoRelease(
                    release_id=rid,
                    organisation_id=organisation_id,
                    proposal_id=proposal_id,
                    version=version,
                    components=components or prop.proposed_change or {},
                    status="STAGED",
                    canary_percent=0,
                    rollback_target="previous",
                )
            )
            prop.status = "STAGED"
        bus.publish("evolution.release.staged", {"release_id": rid}, organisation_id=organisation_id)
        return {"release_id": rid, "status": "STAGED", "version": version}

    def canary(self, organisation_id: str, release_id: str, percent: int) -> Dict[str, Any]:
        if change_freeze.frozen or change_freeze.emergency_stop:
            raise AuthorizationError("Change freeze active")
        if percent < 0 or percent > 100:
            raise ValidationError("canary percent 0-100")
        with UnitOfWork() as uow:
            rel = uow.session.get(EvoRelease, release_id)
            if not rel or rel.organisation_id != organisation_id:
                from core.errors import NotFoundError
                raise NotFoundError("Release not found")
            if rel.status not in ("STAGED", "CANARY", "DEPLOYED"):
                raise ValidationError(f"Cannot canary from status {rel.status}")
            rel.canary_percent = percent
            rel.status = "CANARY" if percent < 100 else "DEPLOYED"
            rel.updated_at = datetime.utcnow()
            st = rel.status
        bus.publish(
            "evolution.release.canary",
            {"release_id": release_id, "percent": percent},
            organisation_id=organisation_id,
        )
        return {"release_id": release_id, "status": st, "canary_percent": percent}

    def promote(self, organisation_id: str, release_id: str) -> Dict[str, Any]:
        return self.canary(organisation_id, release_id, 100)

    def rollback(self, organisation_id: str, release_id: str, reason: str = "") -> Dict[str, Any]:
        with UnitOfWork() as uow:
            rel = uow.session.get(EvoRelease, release_id)
            if not rel or rel.organisation_id != organisation_id:
                from core.errors import NotFoundError
                raise NotFoundError("Release not found")
            prev = rel.status
            rel.status = "ROLLED_BACK"
            rel.canary_percent = 0
            rel.updated_at = datetime.utcnow()
            if rel.proposal_id:
                prop = uow.session.get(EvoProposal, rel.proposal_id)
                if prop:
                    prop.status = "ROLLED_BACK"
        bus.publish(
            "evolution.release.rolled_back",
            {"release_id": release_id, "from": prev, "reason": reason},
            organisation_id=organisation_id,
        )
        return {"release_id": release_id, "status": "ROLLED_BACK", "reason": reason}

    def auto_rollback_on_regression(
        self, organisation_id: str, release_id: str, *, error_rate: float, threshold: float = 0.2
    ) -> Optional[Dict]:
        if error_rate >= threshold:
            return self.rollback(organisation_id, release_id, reason=f"error_rate {error_rate} >= {threshold}")
        return None
