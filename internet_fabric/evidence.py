"""Evidence fabric, claims, conflicts, citation — no fabricated sources."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from internet_fabric.models_db import InternetClaim, InternetConflict, InternetEvidence


class EvidenceFabric:
    def add(
        self,
        organisation_id: str,
        *,
        research_id: Optional[str] = None,
        source_id: Optional[str] = None,
        source_url: str = "",
        source_location: str = "",
        extracted_text: str = "",
        extraction_method: str = "text",
        agent_id: Optional[str] = None,
        structured_value: Optional[Dict[str, Any]] = None,
    ) -> dict:
        eid = new_id("EV-")
        with UnitOfWork() as uow:
            uow.session.add(
                InternetEvidence(
                    evidence_id=eid,
                    organisation_id=organisation_id,
                    research_id=research_id,
                    source_id=source_id,
                    source_url=source_url,
                    source_location=source_location,
                    extracted_text=(extracted_text or "")[:8000],
                    structured_value=structured_value or {},
                    extraction_method=extraction_method,
                    confidence="unverified",
                    agent_id=agent_id,
                    trust="UNTRUSTED_EXTERNAL_CONTENT",
                )
            )
        return {
            "evidence_id": eid,
            "source_id": source_id,
            "source_url": source_url,
            "source_location": source_location,
            "extracted_text": (extracted_text or "")[:500],
            "trust": "UNTRUSTED_EXTERNAL_CONTENT",
            "confidence": "unverified",
        }

    def list_for_research(self, organisation_id: str, research_id: str) -> List[dict]:
        with UnitOfWork() as uow:
            rows = (
                uow.session.query(InternetEvidence)
                .filter_by(organisation_id=organisation_id, research_id=research_id)
                .all()
            )
            return [
                {
                    "evidence_id": r.evidence_id,
                    "source_id": r.source_id,
                    "source_url": r.source_url,
                    "source_location": r.source_location,
                    "extracted_text": (r.extracted_text or "")[:500],
                    "trust": r.trust,
                    "confidence": r.confidence,
                }
                for r in rows
            ]


class ClaimVerifier:
    def record_claim(
        self,
        organisation_id: str,
        statement: str,
        *,
        research_id: Optional[str] = None,
        supporting: Optional[List[str]] = None,
        contradicting: Optional[List[str]] = None,
    ) -> dict:
        supporting = supporting or []
        contradicting = contradicting or []
        if supporting and contradicting:
            status = "CONTESTED"
        elif supporting and not contradicting:
            status = "SUPPORTED"
        elif contradicting and not supporting:
            status = "CONTRADICTED"
        else:
            status = "UNKNOWN"
        cid = new_id("CL-")
        with UnitOfWork() as uow:
            uow.session.add(
                InternetClaim(
                    claim_id=cid,
                    organisation_id=organisation_id,
                    research_id=research_id,
                    statement=statement,
                    status=status,
                    supporting_evidence_ids=supporting,
                    contradicting_evidence_ids=contradicting,
                )
            )
        return {"claim_id": cid, "statement": statement, "status": status}

    def record_conflict(
        self,
        organisation_id: str,
        claim: str,
        source_a_id: str,
        source_b_id: str,
        *,
        research_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> dict:
        xid = new_id("CF-")
        with UnitOfWork() as uow:
            uow.session.add(
                InternetConflict(
                    conflict_id=xid,
                    organisation_id=organisation_id,
                    research_id=research_id,
                    claim=claim,
                    source_a_id=source_a_id,
                    source_b_id=source_b_id,
                    details=details or {},
                    resolution_status="OPEN",
                )
            )
        return {
            "conflict_id": xid,
            "claim": claim,
            "source_a_id": source_a_id,
            "source_b_id": source_b_id,
            "resolution_status": "OPEN",
        }


def build_citations(sources: List[dict], evidence: List[dict]) -> List[dict]:
    """Citations only from real registered sources — never fabricated."""
    by_id = {s["source_id"]: s for s in sources}
    cites = []
    for ev in evidence:
        src = by_id.get(ev.get("source_id") or "")
        if not src:
            cites.append(
                {
                    "status": "SOURCE_NOT_VERIFIED",
                    "evidence_id": ev.get("evidence_id"),
                    "source_url": ev.get("source_url") or None,
                }
            )
            continue
        if src.get("access_status") != "OK":
            cites.append(
                {
                    "status": "SOURCE_NOT_VERIFIED",
                    "reason": src.get("access_status"),
                    "url": src.get("url"),
                    "evidence_id": ev.get("evidence_id"),
                }
            )
            continue
        cites.append(
            {
                "status": "OK",
                "url": src["url"],
                "title": src.get("title"),
                "source_category": src.get("source_category"),
                "retrieved_at": src.get("retrieved_at"),
                "source_location": ev.get("source_location"),
                "evidence_id": ev.get("evidence_id"),
                "trust": "UNTRUSTED_EXTERNAL_CONTENT",
            }
        )
    return cites
