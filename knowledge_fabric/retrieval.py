"""Semantic, lexical, and hybrid retrieval with inspectable ranking."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from knowledge_fabric.embeddings import cosine, get_embedding_provider
from schemas.common import new_id


@dataclass
class RetrievalHit:
    chunk_id: str
    document_id: str
    source_id: str
    content: str
    semantic_score: float = 0.0
    lexical_score: float = 0.0
    recency_score: float = 0.0
    source_score: float = 0.0
    final_score: float = 0.0
    ranking_reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


def lexical_score(query: str, text: str) -> float:
    q_tokens = set(re.findall(r"[a-z0-9]+", (query or "").lower()))
    if not q_tokens:
        return 0.0
    t_tokens = set(re.findall(r"[a-z0-9]+", (text or "").lower()))
    if not t_tokens:
        return 0.0
    inter = q_tokens & t_tokens
    # phrase boost
    phrase = 1.0 if (query or "").lower() in (text or "").lower() else 0.0
    return min(1.0, len(inter) / max(1, len(q_tokens)) + 0.25 * phrase)


def hybrid_rank(
    hits: List[RetrievalHit],
    *,
    w_semantic: float = 0.45,
    w_lexical: float = 0.35,
    w_recency: float = 0.10,
    w_source: float = 0.10,
) -> List[RetrievalHit]:
    for h in hits:
        h.final_score = (
            w_semantic * h.semantic_score
            + w_lexical * h.lexical_score
            + w_recency * h.recency_score
            + w_source * h.source_score
        )
        h.ranking_reason = (
            f"sem={h.semantic_score:.3f} lex={h.lexical_score:.3f} "
            f"rec={h.recency_score:.3f} src={h.source_score:.3f}"
        )
    hits.sort(key=lambda x: x.final_score, reverse=True)
    return hits


class RetrievalEngine:
    def search(
        self,
        *,
        organisation_id: str,
        query: str,
        top_k: int = 10,
        strategy: str = "hybrid",  # semantic|lexical|hybrid
        source_ids: Optional[List[str]] = None,
        min_score: float = 0.0,
        include_invalidated: bool = False,
        requester: Optional[str] = None,
        agent_key: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        from persistence.unit_of_work import UnitOfWork
        from knowledge_fabric.models_db import KFChunk, KFEmbedding, KFSource, KFRetrievalTrace

        t0 = time.time()
        provider = get_embedding_provider()
        q_vec = provider.embed_one(query) if strategy in ("semantic", "hybrid") else None

        with UnitOfWork() as uow:
            q = uow.session.query(KFChunk).filter_by(organisation_id=organisation_id)
            if not include_invalidated:
                q = q.filter(KFChunk.status == "active")
            if source_ids:
                q = q.filter(KFChunk.source_id.in_(source_ids))
            chunks = q.limit(5000).all()  # bounded; index filters applied

            # Permission: only sources readable by org (org_read default)
            allowed_sources = set()
            for s in (
                uow.session.query(KFSource)
                .filter_by(organisation_id=organisation_id)
                .filter(KFSource.status == "active")
                .all()
            ):
                perms = s.permissions or ["org_read"]
                if "org_read" in perms or "public" in perms:
                    allowed_sources.add(s.source_id)
                # restricted without org_read skipped
                if "restricted" in perms and "org_read" not in perms:
                    if s.source_id in allowed_sources:
                        allowed_sources.discard(s.source_id)

            hits: List[RetrievalHit] = []
            emb_by_chunk: Dict[str, List[float]] = {}
            if q_vec is not None and chunks:
                chunk_ids = [c.chunk_id for c in chunks]
                embs = (
                    uow.session.query(KFEmbedding)
                    .filter(
                        KFEmbedding.organisation_id == organisation_id,
                        KFEmbedding.chunk_id.in_(chunk_ids),
                        KFEmbedding.status == "active",
                        KFEmbedding.model == provider.model,
                    )
                    .all()
                )
                for e in embs:
                    emb_by_chunk[e.chunk_id] = e.vector or []

            for c in chunks:
                if c.source_id not in allowed_sources and allowed_sources:
                    # if we have permission map, enforce; empty allowed means no sources registered yet
                    src = uow.session.get(KFSource, c.source_id)
                    if src and "restricted" in (src.permissions or []):
                        continue
                    if src and src.organisation_id != organisation_id:
                        continue
                sem = cosine(q_vec, emb_by_chunk[c.chunk_id]) if q_vec and c.chunk_id in emb_by_chunk else 0.0
                lex = lexical_score(query, c.content)
                if strategy == "semantic" and sem < min_score:
                    continue
                if strategy == "lexical" and lex < min_score:
                    continue
                hits.append(
                    RetrievalHit(
                        chunk_id=c.chunk_id,
                        document_id=c.document_id,
                        source_id=c.source_id,
                        content=c.content,
                        semantic_score=sem,
                        lexical_score=lex,
                        recency_score=0.5,
                        source_score=0.5,
                        metadata={
                            "heading": c.heading,
                            "page": c.page,
                            "section": c.section,
                            "ordinal": c.ordinal,
                        },
                    )
                )

            if strategy == "semantic":
                hits.sort(key=lambda h: h.semantic_score, reverse=True)
                for h in hits:
                    h.final_score = h.semantic_score
                    h.ranking_reason = f"sem={h.semantic_score:.3f}"
            elif strategy == "lexical":
                hits.sort(key=lambda h: h.lexical_score, reverse=True)
                for h in hits:
                    h.final_score = h.lexical_score
                    h.ranking_reason = f"lex={h.lexical_score:.3f}"
            else:
                hits = hybrid_rank(hits)

            hits = [h for h in hits if h.final_score >= min_score][:top_k]
            selected = [
                {
                    "chunk_id": h.chunk_id,
                    "document_id": h.document_id,
                    "source_id": h.source_id,
                    "final_score": h.final_score,
                    "ranking_reason": h.ranking_reason,
                    "content_preview": (h.content or "")[:200],
                    "metadata": h.metadata,
                }
                for h in hits
            ]
            rid = new_id("RET-")
            latency = int((time.time() - t0) * 1000)
            uow.session.add(
                KFRetrievalTrace(
                    retrieval_id=rid,
                    organisation_id=organisation_id,
                    requester=requester,
                    agent_key=agent_key,
                    task_id=task_id,
                    query=query,
                    strategy=strategy,
                    filters={"source_ids": source_ids, "min_score": min_score},
                    result_count=len(hits),
                    selected=selected,
                    ranking=[{"chunk_id": h.chunk_id, "final_score": h.final_score, "reason": h.ranking_reason} for h in hits],
                    latency_ms=latency,
                )
            )
        return {
            "retrieval_id": rid,
            "strategy": strategy,
            "hits": [
                {
                    "chunk_id": h.chunk_id,
                    "document_id": h.document_id,
                    "source_id": h.source_id,
                    "content": h.content,
                    "semantic_score": h.semantic_score,
                    "lexical_score": h.lexical_score,
                    "final_score": h.final_score,
                    "ranking_reason": h.ranking_reason,
                    "metadata": h.metadata,
                }
                for h in hits
            ],
            "latency_ms": latency,
        }
