"""Improvement proposals — evidence-required, version-hashed."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.errors import AuthorizationError, ValidationError
from events.bus import bus
from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from evolution.governance import is_prohibited, risk_for, change_freeze
from evolution.models_db import EvoProposal


def _hash_change(proposed_change: Dict) -> str:
    raw = json.dumps(proposed_change or {}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


class ProposalService:
    def create(
        self,
        organisation_id: str,
        *,
        title: str,
        category: str,
        proposed_change: Dict[str, Any],
        evidence: Optional[Dict] = None,
        detected_problem: str = "",
        description: str = "",
        source: str = "observation",
        root_cause: str = "",
        root_cause_status: str = "NEEDS_MORE_EVIDENCE",
        baseline: Optional[Dict] = None,
        expected_effect: str = "",
        affected_components: Optional[List] = None,
        evaluation_plan: Optional[Dict] = None,
        rollback_plan: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        if not title or not category:
            raise ValidationError("title and category required")
        if not evidence:
            raise ValidationError("Evidence is required for every proposal")
        if change_freeze.emergency_stop:
            raise AuthorizationError("Emergency stop active — no new proposals")

        risk = risk_for(category)
        if is_prohibited(category) and risk.value.endswith("4"):
            # still allow proposal creation for human review, but flag
            pass

        pid = new_id("PROP-")
        ch = _hash_change(proposed_change)
        with UnitOfWork() as uow:
            uow.session.add(
                EvoProposal(
                    proposal_id=pid,
                    organisation_id=organisation_id,
                    title=title,
                    description=description,
                    category=category,
                    risk_level=risk.value,
                    source=source,
                    detected_problem=detected_problem,
                    evidence=evidence,
                    root_cause=root_cause,
                    root_cause_status=root_cause_status,
                    baseline=baseline or {},
                    proposed_change=proposed_change,
                    expected_effect=expected_effect,
                    affected_components=affected_components or [],
                    evaluation_plan=evaluation_plan or {},
                    rollback_plan=rollback_plan or {"strategy": "restore_previous_version"},
                    status="PROPOSED",
                    content_hash=ch,
                )
            )
        bus.publish(
            "evolution.proposal.created",
            {"proposal_id": pid, "category": category, "risk": risk.value},
            organisation_id=organisation_id,
        )
        return {
            "proposal_id": pid,
            "category": category,
            "risk_level": risk.value,
            "status": "PROPOSED",
            "content_hash": ch,
            "prohibited_auto": is_prohibited(category),
        }

    def get(self, proposal_id: str, organisation_id: str) -> Optional[Dict]:
        with UnitOfWork() as uow:
            row = uow.session.get(EvoProposal, proposal_id)
            if not row or row.organisation_id != organisation_id:
                return None
            return self._to_dict(row)

    def list(self, organisation_id: str, status: Optional[str] = None, limit: int = 50) -> List[Dict]:
        with UnitOfWork() as uow:
            q = uow.session.query(EvoProposal).filter_by(organisation_id=organisation_id)
            if status:
                q = q.filter_by(status=status)
            rows = q.order_by(EvoProposal.created_at.desc()).limit(limit).all()
            return [self._to_dict(r) for r in rows]

    def update_change(
        self, proposal_id: str, organisation_id: str, proposed_change: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Modifying proposed_change invalidates prior approvals (hash change)."""
        with UnitOfWork() as uow:
            row = uow.session.get(EvoProposal, proposal_id)
            if not row or row.organisation_id != organisation_id:
                from core.errors import NotFoundError
                raise NotFoundError("Proposal not found")
            row.proposed_change = proposed_change
            row.content_hash = _hash_change(proposed_change)
            row.updated_at = datetime.utcnow()
            row.status = "PROPOSED"  # reset
            h = row.content_hash
        bus.publish(
            "evolution.proposal.modified",
            {"proposal_id": proposal_id, "content_hash": h},
            organisation_id=organisation_id,
        )
        return {"proposal_id": proposal_id, "content_hash": h, "approvals_invalidated": True}

    def set_status(self, proposal_id: str, organisation_id: str, status: str) -> Dict:
        with UnitOfWork() as uow:
            row = uow.session.get(EvoProposal, proposal_id)
            if not row or row.organisation_id != organisation_id:
                from core.errors import NotFoundError
                raise NotFoundError("Proposal not found")
            row.status = status
            row.updated_at = datetime.utcnow()
        return {"proposal_id": proposal_id, "status": status}

    def _to_dict(self, row: EvoProposal) -> Dict:
        return {
            "proposal_id": row.proposal_id,
            "title": row.title,
            "category": row.category,
            "risk_level": row.risk_level,
            "status": row.status,
            "evidence": row.evidence,
            "root_cause_status": row.root_cause_status,
            "proposed_change": row.proposed_change,
            "content_hash": row.content_hash,
            "prohibited_auto": is_prohibited(row.category),
        }
