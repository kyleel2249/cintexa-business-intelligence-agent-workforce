"""Drift detection, knowledge candidates, feedback."""

from __future__ import annotations

from typing import Any, Dict, Optional

from events.bus import bus
from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from evolution.models_db import EvoDrift, EvoFeedback, EvoKnowledgeCandidate


class DriftService:
    def record(
        self,
        organisation_id: str,
        kind: str,
        *,
        metric: str = "",
        baseline_value: Optional[float] = None,
        current_value: Optional[float] = None,
        details: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        did = new_id("DFT-")
        with UnitOfWork() as uow:
            uow.session.add(
                EvoDrift(
                    drift_id=did,
                    organisation_id=organisation_id,
                    kind=kind,
                    metric=metric,
                    baseline_value=baseline_value,
                    current_value=current_value,
                    details=details or {},
                )
            )
        bus.publish("evolution.drift.detected", {"drift_id": did, "kind": kind}, organisation_id=organisation_id)
        return {"drift_id": did, "kind": kind, "status": "DETECTED"}


class KnowledgePromotion:
    def propose(
        self,
        organisation_id: str,
        content: str,
        provenance: Dict[str, Any],
        trust: str = "UNVERIFIED",
    ) -> Dict[str, Any]:
        """Never auto-promote model output to trusted knowledge."""
        if trust not in ("UNVERIFIED", "SOURCE_VERIFIED", "USER_CONFIRMED", "AGENT_DERIVED"):
            trust = "UNVERIFIED"
        if trust == "AGENT_DERIVED":
            # cannot jump to promoted
            pass
        cid = new_id("KC-")
        with UnitOfWork() as uow:
            uow.session.add(
                EvoKnowledgeCandidate(
                    candidate_id=cid,
                    organisation_id=organisation_id,
                    content=content,
                    provenance=provenance,
                    trust=trust,
                    status="CANDIDATE",
                )
            )
        return {"candidate_id": cid, "status": "CANDIDATE", "trust": trust}

    def promote(
        self, organisation_id: str, candidate_id: str, *, authorized: bool = False, trust: str = "USER_CONFIRMED"
    ) -> Dict[str, Any]:
        if not authorized:
            from core.errors import AuthorizationError
            raise AuthorizationError("Knowledge promotion requires authorization")
        if trust not in ("SOURCE_VERIFIED", "USER_CONFIRMED"):
            from core.errors import ValidationError
            raise ValidationError("Cannot promote with insufficient trust level")
        with UnitOfWork() as uow:
            row = uow.session.get(EvoKnowledgeCandidate, candidate_id)
            if not row or row.organisation_id != organisation_id:
                from core.errors import NotFoundError
                raise NotFoundError("Candidate not found")
            row.status = "PROMOTED"
            row.trust = trust
        # optional: ingest into Knowledge Fabric
        try:
            from knowledge_fabric.service import KnowledgeFabric
            KnowledgeFabric().ingest_document(
                organisation_id=organisation_id,
                content=row.content if row else "",
                title="promoted-knowledge",
                source_type="promoted",
            )
        except Exception:
            pass
        return {"candidate_id": candidate_id, "status": "PROMOTED", "trust": trust}


class FeedbackService:
    def submit(
        self,
        organisation_id: str,
        kind: str,
        content: str,
        *,
        execution_id: Optional[str] = None,
        agent_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        fid = new_id("FB-")
        with UnitOfWork() as uow:
            uow.session.add(
                EvoFeedback(
                    feedback_id=fid,
                    organisation_id=organisation_id,
                    kind=kind,
                    content=content,
                    execution_id=execution_id,
                    agent_key=agent_key,
                )
            )
        return {"feedback_id": fid, "kind": kind}
