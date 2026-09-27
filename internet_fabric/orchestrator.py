"""Internet Research Orchestrator — multi-step research without fabricating access."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

from events.bus import bus
from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from external_fabric.url_security import UrlPolicy, validate_url, UrlSecurityError
from external_fabric.browser import BrowserEngine
from internet_fabric.models_db import InternetResearchCase
from internet_fabric.search import SearchFabric
from internet_fabric.sources import SourceRegistry
from internet_fabric.evidence import EvidenceFabric, ClaimVerifier, build_citations


DEFAULT_BUDGET = {
    "max_queries": 5,
    "max_pages": 8,
    "max_domains": 10,
    "max_runtime_sec": 120,
}


class InternetResearchOrchestrator:
    """Coordinates search → retrieve → extract → evidence → synthesis.

    Integrates external_fabric browser + URL security; does not bypass policy.
    """

    def __init__(
        self,
        search: Optional[SearchFabric] = None,
        browser: Optional[BrowserEngine] = None,
    ):
        self.search = search or SearchFabric()
        self.browser = browser or BrowserEngine()
        self.sources = SourceRegistry()
        self.evidence = EvidenceFabric()
        self.claims = ClaimVerifier()

    def research(
        self,
        organisation_id: str,
        question: str,
        *,
        depth: str = "STANDARD",
        seed_urls: Optional[List[str]] = None,
        permissions: Optional[Set[str]] = None,
        budget: Optional[Dict[str, int]] = None,
        agent_id: Optional[str] = None,
    ) -> dict:
        permissions = permissions or {"web:search", "web:read", "web:research", "*"}
        budget = {**DEFAULT_BUDGET, **(budget or {})}
        rid = new_id("RES-")
        queries = self._plan_queries(question, depth)
        methodology = {
            "depth": depth,
            "query_families": queries,
            "note": "External content treated as UNTRUSTED_EXTERNAL_CONTENT",
        }
        with UnitOfWork() as uow:
            uow.session.add(
                InternetResearchCase(
                    research_id=rid,
                    organisation_id=organisation_id,
                    agent_id=agent_id,
                    question=question,
                    depth=depth,
                    status="SEARCHING",
                    methodology=methodology,
                    budget=budget,
                    budget_used={"queries": 0, "pages": 0},
                )
            )
        bus.publish(
            "internet.research.started",
            {"research_id": rid, "question": question[:300]},
            organisation_id=organisation_id,
        )

        all_hits = []
        queries_used = 0
        for q in queries:
            if queries_used >= budget["max_queries"]:
                break
            result = self.search.search(
                organisation_id, q, research_id=rid, max_results=8
            )
            queries_used += 1
            if result.status == "OK":
                all_hits.extend(result.hits)

        # Deduplicate by URL
        seen = set()
        unique_hits = []
        for h in all_hits:
            if h.url not in seen:
                seen.add(h.url)
                unique_hits.append(h)

        seed_urls = list(seed_urls or [])
        for h in unique_hits:
            if h.url not in seed_urls:
                seed_urls.append(h.url)

        pages_used = 0
        domains: Set[str] = set()
        source_records = []
        evidence_records = []
        limitations = []
        sess = None

        try:
            sess = self.browser.create_session(organisation_id, agent_id=agent_id)
            for url in seed_urls:
                if pages_used >= budget["max_pages"]:
                    limitations.append("max_pages budget exhausted")
                    break
                domain = urlparse(url).hostname or ""
                if domain and len(domains) >= budget["max_domains"] and domain not in domains:
                    continue
                try:
                    validate_url(url, UrlPolicy())
                except UrlSecurityError as e:
                    src = self.sources.register(
                        organisation_id,
                        url,
                        research_id=rid,
                        access_status="BLOCKED_BY_POLICY",
                        meta={"error": str(e)},
                    )
                    source_records.append(src)
                    limitations.append(f"BLOCKED_BY_POLICY: {url}")
                    continue

                nav = self.browser.navigate(
                    sess["session_id"], organisation_id, url, permissions=permissions
                )
                if nav.get("status") == "CAPTCHA_DETECTED":
                    src = self.sources.register(
                        organisation_id, url, research_id=rid, access_status="ACCESS_RESTRICTED"
                    )
                    source_records.append(src)
                    limitations.append(f"ACCESS_RESTRICTED (CAPTCHA): {url}")
                    continue
                if nav.get("status") not in ("OK",):
                    # still try observe if mock returned content
                    pass

                try:
                    obs = self.browser.observe(sess["session_id"], organisation_id, url)
                except Exception as e:
                    src = self.sources.register(
                        organisation_id,
                        url,
                        research_id=rid,
                        access_status="ACCESS_FAILED",
                        meta={"error": str(e)[:200]},
                    )
                    source_records.append(src)
                    limitations.append(f"ACCESS_FAILED: {url}")
                    continue

                pages_used += 1
                if domain:
                    domains.add(domain)
                title = obs.get("title") or ""
                text = obs.get("visible_text") or ""
                ch = obs.get("content_hash")
                src = self.sources.register(
                    organisation_id,
                    url,
                    research_id=rid,
                    title=title,
                    access_status="OK",
                    content_hash=ch,
                    meta={"trust": obs.get("trust", "UNTRUSTED_EXTERNAL_CONTENT")},
                )
                source_records.append(src)
                ev = self.evidence.add(
                    organisation_id,
                    research_id=rid,
                    source_id=src["source_id"],
                    source_url=url,
                    source_location="visible_text",
                    extracted_text=text,
                    extraction_method="browser.observe",
                    agent_id=agent_id,
                )
                evidence_records.append(ev)
        finally:
            if sess:
                try:
                    self.browser.close(sess["session_id"], organisation_id)
                except Exception:
                    pass

        # Simple claim from question tokens vs evidence (supported if any evidence has related text)
        q_tokens = [t for t in question.lower().split() if len(t) > 3][:5]
        supporting = []
        for ev in evidence_records:
            text_l = (ev.get("extracted_text") or "").lower()
            if any(t in text_l for t in q_tokens):
                supporting.append(ev["evidence_id"])
        claim = self.claims.record_claim(
            organisation_id,
            statement=f"Research findings related to: {question[:200]}",
            research_id=rid,
            supporting=supporting[:5],
        )
        citations = build_citations(source_records, evidence_records)
        findings = []
        for ev in evidence_records[:10]:
            findings.append(
                {
                    "summary": (ev.get("extracted_text") or "")[:240],
                    "source_url": ev.get("source_url"),
                    "evidence_id": ev.get("evidence_id"),
                    "trust": "UNTRUSTED_EXTERNAL_CONTENT",
                    "confidence": "unverified",
                }
            )
        if not findings:
            limitations.append("No pages successfully retrieved; findings empty")
            unanswered = [question]
        else:
            unanswered = []

        status = "COMPLETED"
        with UnitOfWork() as uow:
            row = uow.session.get(InternetResearchCase, rid)
            if row and row.organisation_id == organisation_id:
                row.status = status
                row.findings = findings
                row.limitations = limitations
                row.unanswered = unanswered
                row.budget_used = {"queries": queries_used, "pages": pages_used}
                row.completed_at = datetime.utcnow()

        bus.publish(
            "internet.research.completed",
            {"research_id": rid, "sources": len(source_records), "evidence": len(evidence_records)},
            organisation_id=organisation_id,
        )

        return {
            "research_id": rid,
            "question": question,
            "status": status,
            "methodology": methodology,
            "sources": source_records,
            "evidence": evidence_records,
            "claims": [claim],
            "findings": findings,
            "limitations": limitations,
            "unanswered_questions": unanswered,
            "citations": citations,
            "budget_used": {"queries": queries_used, "pages": pages_used},
            "trust_policy": "UNTRUSTED_EXTERNAL_CONTENT",
        }

    def get_research(self, organisation_id: str, research_id: str) -> dict:
        with UnitOfWork() as uow:
            row = uow.session.get(InternetResearchCase, research_id)
            if not row or row.organisation_id != organisation_id:
                from core.errors import NotFoundError
                raise NotFoundError("Research case not found")
            return {
                "research_id": row.research_id,
                "question": row.question,
                "status": row.status,
                "depth": row.depth,
                "methodology": row.methodology,
                "findings": row.findings,
                "limitations": row.limitations,
                "unanswered_questions": row.unanswered,
                "budget": row.budget,
                "budget_used": row.budget_used,
                "sources": self.sources.list_for_research(organisation_id, research_id),
                "evidence": self.evidence.list_for_research(organisation_id, research_id),
            }

    def _plan_queries(self, question: str, depth: str) -> List[str]:
        base = question.strip()
        queries = [base]
        if depth in ("STANDARD", "DEEP", "EXHAUSTIVE"):
            queries.append(f"{base} documentation")
            queries.append(f"{base} official")
        if depth in ("DEEP", "EXHAUSTIVE"):
            queries.append(f"{base} analysis")
            queries.append(f"{base} limitations OR risks")
        if depth == "EXHAUSTIVE":
            queries.append(f"{base} alternative")
            queries.append(f"{base} historical")
        # dedupe preserve order
        out, seen = [], set()
        for q in queries:
            if q not in seen:
                seen.add(q)
                out.append(q)
        return out
