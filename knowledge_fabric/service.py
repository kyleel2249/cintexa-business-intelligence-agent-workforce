"""Knowledge Fabric — ingestion, entities, claims, evidence, provenance."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from core.errors import NotFoundError, ValidationError
from events.bus import bus
from knowledge_fabric.chunking import ChunkConfig, chunk_text, deterministic_chunk_id
from knowledge_fabric.embeddings import get_embedding_provider
from knowledge_fabric.retrieval import RetrievalEngine
from knowledge_fabric.models_db import (
    KFClaim,
    KFChunk,
    KFDocument,
    KFEmbedding,
    KFEntity,
    KFEvidence,
    KFRelationship,
    KFSource,
)
from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id


class KnowledgeFabric:
    def __init__(self):
        self.retrieval = RetrievalEngine()

    # ── Sources & documents ─────────────────────────────────────

    def create_source(
        self,
        *,
        organisation_id: str,
        source_type: str,
        title: str = "",
        location: Optional[str] = None,
        reliability: str = "UNVERIFIED",
        permissions: Optional[List[str]] = None,
        owner_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        sid = new_id("SRC-")
        with UnitOfWork() as uow:
            src = KFSource(
                source_id=sid,
                organisation_id=organisation_id,
                source_type=source_type,
                title=title,
                location=location,
                reliability=reliability,
                permissions=permissions or ["org_read"],
                owner_id=owner_id,
                metadata_json=metadata or {},
                observed_at=datetime.utcnow(),
            )
            uow.session.add(src)
        bus.publish("knowledge.source.created", {"source_id": sid}, organisation_id=organisation_id)
        return {"source_id": sid, "organisation_id": organisation_id, "source_type": source_type}

    def ingest_document(
        self,
        *,
        organisation_id: str,
        content: str,
        title: str = "",
        content_type: str = "text/plain",
        source_id: Optional[str] = None,
        source_type: str = "document",
        chunk_config: Optional[ChunkConfig] = None,
        permissions: Optional[List[str]] = None,
        embed: bool = True,
    ) -> Dict[str, Any]:
        if not content:
            raise ValidationError("Document content required")
        if not source_id:
            src = self.create_source(
                organisation_id=organisation_id,
                source_type=source_type,
                title=title,
                permissions=permissions,
            )
            source_id = src["source_id"]
        doc_id = new_id("DOC-")
        specs = chunk_text(content, chunk_config)
        provider = get_embedding_provider()
        vectors = provider.embed([s.content for s in specs]) if embed and specs else []

        with UnitOfWork() as uow:
            uow.session.add(
                KFDocument(
                    document_id=doc_id,
                    organisation_id=organisation_id,
                    source_id=source_id,
                    title=title,
                    content_type=content_type,
                    content=content,
                    status="indexed" if embed else "processed",
                    metadata_json={"chunk_count": len(specs)},
                )
            )
            chunk_ids = []
            for i, spec in enumerate(specs):
                cid = deterministic_chunk_id(doc_id, spec.ordinal)
                chunk_ids.append(cid)
                uow.session.add(
                    KFChunk(
                        chunk_id=cid,
                        organisation_id=organisation_id,
                        document_id=doc_id,
                        source_id=source_id,
                        ordinal=spec.ordinal,
                        content=spec.content,
                        heading=spec.heading,
                        page=spec.page,
                        section=spec.section,
                        token_estimate=spec.token_estimate,
                    )
                )
                if embed and i < len(vectors):
                    uow.session.add(
                        KFEmbedding(
                            embedding_id=new_id("EMB-"),
                            organisation_id=organisation_id,
                            chunk_id=cid,
                            provider=provider.provider,
                            model=provider.model,
                            dimensions=provider.dimensions,
                            vector=vectors[i],
                            embedding_version=provider.version,
                        )
                    )
        bus.publish(
            "document.ingested",
            {"document_id": doc_id, "source_id": source_id, "chunks": len(specs)},
            organisation_id=organisation_id,
        )
        return {
            "document_id": doc_id,
            "source_id": source_id,
            "chunk_count": len(specs),
            "chunk_ids": chunk_ids,
            "status": "indexed" if embed else "processed",
        }

    def invalidate_source(self, source_id: str, organisation_id: str) -> None:
        with UnitOfWork() as uow:
            src = uow.session.get(KFSource, source_id)
            if not src or src.organisation_id != organisation_id:
                raise NotFoundError("Source not found")
            src.status = "invalidated"
            for c in uow.session.query(KFChunk).filter_by(source_id=source_id, organisation_id=organisation_id):
                c.status = "invalidated"
            for e in uow.session.query(KFEmbedding).filter_by(organisation_id=organisation_id).all():
                # invalidate embeddings for chunks of this source
                ch = uow.session.get(KFChunk, e.chunk_id)
                if ch and ch.source_id == source_id:
                    e.status = "invalidated"
        bus.publish("knowledge.invalidated", {"source_id": source_id}, organisation_id=organisation_id)

    def search(self, **kwargs) -> Dict[str, Any]:
        return self.retrieval.search(**kwargs)

    # ── Entities & relationships ────────────────────────────────

    def upsert_entity(
        self,
        *,
        organisation_id: str,
        entity_type: str,
        canonical_name: str,
        aliases: Optional[List[str]] = None,
        confidence: float = 0.5,
        provenance: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        with UnitOfWork() as uow:
            existing = (
                uow.session.query(KFEntity)
                .filter_by(organisation_id=organisation_id, entity_type=entity_type, canonical_name=canonical_name)
                .filter(KFEntity.status == "active")
                .one_or_none()
            )
            if existing:
                if aliases:
                    existing.aliases = list({*(existing.aliases or []), *aliases})
                eid = existing.entity_id
            else:
                # soft resolution: match alias
                rows = (
                    uow.session.query(KFEntity)
                    .filter_by(organisation_id=organisation_id, entity_type=entity_type, status="active")
                    .all()
                )
                resolved = None
                name_l = canonical_name.lower().strip()
                for r in rows:
                    names = [r.canonical_name.lower()] + [a.lower() for a in (r.aliases or [])]
                    if name_l in names or name_l.replace(" ", "") in [n.replace(" ", "") for n in names]:
                        resolved = r
                        break
                if resolved:
                    aliases_merged = list({*(resolved.aliases or []), canonical_name, *(aliases or [])})
                    resolved.aliases = aliases_merged
                    eid = resolved.entity_id
                else:
                    eid = new_id("ENT-")
                    uow.session.add(
                        KFEntity(
                            entity_id=eid,
                            organisation_id=organisation_id,
                            entity_type=entity_type,
                            canonical_name=canonical_name,
                            aliases=aliases or [],
                            confidence=confidence,
                            provenance=provenance or {},
                        )
                    )
        bus.publish("entity.created", {"entity_id": eid}, organisation_id=organisation_id)
        return {"entity_id": eid, "canonical_name": canonical_name, "entity_type": entity_type}

    def relate(
        self,
        *,
        organisation_id: str,
        source_entity_id: str,
        relationship_type: str,
        target_entity_id: str,
        confidence: float = 0.5,
        provenance: Optional[Dict] = None,
        valid_from: Optional[datetime] = None,
        valid_until: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        rid = new_id("REL-")
        with UnitOfWork() as uow:
            for eid in (source_entity_id, target_entity_id):
                e = uow.session.get(KFEntity, eid)
                if not e or e.organisation_id != organisation_id:
                    raise NotFoundError(f"Entity {eid} not found in organisation")
            uow.session.add(
                KFRelationship(
                    relationship_id=rid,
                    organisation_id=organisation_id,
                    source_entity_id=source_entity_id,
                    relationship_type=relationship_type,
                    target_entity_id=target_entity_id,
                    confidence=confidence,
                    provenance=provenance or {},
                    valid_from=valid_from,
                    valid_until=valid_until,
                )
            )
        bus.publish("relationship.created", {"relationship_id": rid}, organisation_id=organisation_id)
        return {"relationship_id": rid}

    # ── Claims & evidence ───────────────────────────────────────

    def create_evidence(
        self,
        *,
        organisation_id: str,
        content: str,
        source_id: Optional[str] = None,
        document_id: Optional[str] = None,
        chunk_id: Optional[str] = None,
        claim_id: Optional[str] = None,
        confidence: float = 0.5,
        confidence_kind: str = "source_supported",
        provenance: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        eid = new_id("KEV-")
        with UnitOfWork() as uow:
            uow.session.add(
                KFEvidence(
                    evidence_id=eid,
                    organisation_id=organisation_id,
                    content=content,
                    source_id=source_id,
                    document_id=document_id,
                    chunk_id=chunk_id,
                    claim_id=claim_id,
                    confidence=confidence,
                    confidence_kind=confidence_kind,
                    provenance=provenance or {},
                )
            )
        bus.publish("evidence.created", {"evidence_id": eid}, organisation_id=organisation_id)
        return {"evidence_id": eid}

    def create_claim(
        self,
        *,
        organisation_id: str,
        claim_text: str,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        object_text: Optional[str] = None,
        status: str = "UNVERIFIED",
        confidence: float = 0.5,
        confidence_kind: str = "derived",
        source_id: Optional[str] = None,
        evidence_ids: Optional[List[str]] = None,
        task_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        agent_key: Optional[str] = None,
        valid_from: Optional[datetime] = None,
        valid_until: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        cid = new_id("CLM-")
        with UnitOfWork() as uow:
            uow.session.add(
                KFClaim(
                    claim_id=cid,
                    organisation_id=organisation_id,
                    claim_text=claim_text,
                    subject=subject,
                    predicate=predicate,
                    object_text=object_text,
                    status=status,
                    confidence=confidence,
                    confidence_kind=confidence_kind,
                    source_id=source_id,
                    evidence_ids=evidence_ids or [],
                    task_id=task_id,
                    workflow_id=workflow_id,
                    agent_key=agent_key,
                    valid_from=valid_from,
                    valid_until=valid_until,
                    observed_at=datetime.utcnow(),
                )
            )
        bus.publish("claim.created", {"claim_id": cid, "status": status}, organisation_id=organisation_id)
        return {"claim_id": cid, "status": status}

    def find_contradictions(self, organisation_id: str, subject: str, predicate: str) -> List[Dict[str, Any]]:
        with UnitOfWork() as uow:
            rows = (
                uow.session.query(KFClaim)
                .filter_by(organisation_id=organisation_id, subject=subject, predicate=predicate)
                .filter(KFClaim.status != "SUPERSEDED")
                .all()
            )
            # group by object_text
            by_obj: Dict[str, List] = {}
            for r in rows:
                key = (r.object_text or "").strip()
                by_obj.setdefault(key, []).append(r)
            if len(by_obj) <= 1:
                return []
            # mark contradicted
            result = []
            for key, items in by_obj.items():
                for r in items:
                    if r.status == "UNVERIFIED":
                        r.status = "CONTRADICTED"
                    result.append(
                        {
                            "claim_id": r.claim_id,
                            "claim_text": r.claim_text,
                            "object_text": r.object_text,
                            "source_id": r.source_id,
                            "status": r.status,
                            "observed_at": r.observed_at.isoformat() if r.observed_at else None,
                        }
                    )
            return result

    def get_provenance(self, *, organisation_id: str, claim_id: Optional[str] = None, evidence_id: Optional[str] = None) -> Dict[str, Any]:
        """Walk claim → evidence → chunk → document → source."""
        chain: List[Dict[str, Any]] = []
        with UnitOfWork() as uow:
            if claim_id:
                claim = uow.session.get(KFClaim, claim_id)
                if not claim or claim.organisation_id != organisation_id:
                    raise NotFoundError("Claim not found")
                chain.append({"type": "claim", "id": claim.claim_id, "text": claim.claim_text, "status": claim.status})
                for eid in claim.evidence_ids or []:
                    ev = uow.session.get(KFEvidence, eid)
                    if ev and ev.organisation_id == organisation_id:
                        chain.append({"type": "evidence", "id": ev.evidence_id, "content": ev.content[:300]})
                        if ev.chunk_id:
                            ch = uow.session.get(KFChunk, ev.chunk_id)
                            if ch:
                                chain.append({"type": "chunk", "id": ch.chunk_id, "document_id": ch.document_id})
                                doc = uow.session.get(KFDocument, ch.document_id)
                                if doc:
                                    chain.append({"type": "document", "id": doc.document_id, "title": doc.title})
                                    src = uow.session.get(KFSource, doc.source_id)
                                    if src:
                                        chain.append(
                                            {
                                                "type": "source",
                                                "id": src.source_id,
                                                "source_type": src.source_type,
                                                "title": src.title,
                                                "location": src.location,
                                            }
                                        )
            elif evidence_id:
                ev = uow.session.get(KFEvidence, evidence_id)
                if not ev or ev.organisation_id != organisation_id:
                    raise NotFoundError("Evidence not found")
                chain.append({"type": "evidence", "id": ev.evidence_id})
        return {"chain": chain}
