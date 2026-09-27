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
from internet_fabric.strategy import SearchStrategyEngine
from internet_fabric.entities import extract_entities
from internet_fabric.cache import search_cache
from internet_fabric.courtroom_adapter import package_for_courtroom


DEFAULT_BUDGET = {
    "max_queries": 5,
    "max_pages": 8,
    "max_domains": 10,
    "max_runtime_sec": 120,
}


class InternetResearchOrchestrator:
    """Coordinates strategy → search → retrieve → extract → evidence → synthesis.

    Integrates external_fabric browser + URL security; does not bypass policy.
    Does not claim live web access when providers are mocks or blocked.
    """

    def __init__(
        self,
        search: Optional[SearchFabric] = None,
        browser: Optional[BrowserEngine] = None,
        strategy: Optional[SearchStrategyEngine] = None,
    ):
        self.search = search or SearchFabric()
        self.browser = browser or BrowserEngine()
        self.strategy = strategy or SearchStrategyEngine()
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
        budget: Optional[Dict[str, Any]] = None,
        agent_id: Optional[str] = None,
        case_id: Optional[str] = None,
    ) -> dict:
        plan = self.strategy.plan(question, depth=depth, budget=budget)
        budget_use = {
            "max_queries": plan.max_queries,
            "max_pages": plan.max_pages,
            **(budget or {}),
        }
        research_id = new_id("IR-")
        methodology = {
            "depth": plan.depth,
            "query_families": [{"name": f.name, "query": f.query, "purpose": f.purpose} for f in plan.families],
            "budget": budget_use,
            "case_id": case_id,
        }

        with UnitOfWork() as uow:
            uow.session.add(
                InternetResearchCase(
                    research_id=research_id,
                    organisation_id=organisation_id,
                    agent_id=agent_id,
                    question=question,
                    depth=plan.depth,
                    status="SEARCHING",
                    methodology=methodology,
                    budget=budget_use,
                    created_at=datetime.utcnow(),
                )
            )

        sources_out: List[dict] = []
        evidence_out: List[dict] = []
        claims_out: List[dict] = []
        contradictions: List[dict] = []
        findings: List[dict] = []
        limitations: List[str] = []
        unanswered: List[str] = []
        search_logs: List[dict] = []
        used_queries: List[str] = []
        domains: Set[str] = set()
        urls_seen: Set[str] = set()
        pages_retrieved = 0
        queries_used = 0
        stop_reason: Optional[str] = None

        # Seed URLs first (policy-checked)
        for url in seed_urls or []:
            if pages_retrieved >= plan.max_pages:
                break
            src = self._retrieve_url(
                organisation_id, research_id, url, sources_out, evidence_out, limitations, domains, urls_seen
            )
            if src and src.get("access_status") == "OK":
                pages_retrieved += 1

        # Search families + refinement loop
        pending_queries = [f.query for f in plan.families]
        round_idx = 0
        while pending_queries and queries_used < plan.max_queries:
            q = pending_queries.pop(0)
            if q in used_queries:
                continue
            used_queries.append(q)
            queries_used += 1
            round_idx += 1

            cached = search_cache.get(organisation_id, "search", q)
            if cached is not None:
                sres = cached
            else:
                sres = self.search.search(organisation_id, q, research_id=research_id, max_results=8)
                if sres.status == "OK":
                    search_cache.set(organisation_id, "search", q, sres, ttl_sec=120)

            search_logs.extend(sres.logs or [])
            if sres.status != "OK" or not sres.hits:
                limitations.append(f"Search empty/failed for query family round {round_idx}: {sres.status}")
            else:
                for hit in sres.hits:
                    if pages_retrieved >= plan.max_pages:
                        break
                    if len(domains) >= int(budget_use.get("max_domains", 10)):
                        break
                    url = hit.url
                    if url in urls_seen:
                        continue
                    host = urlparse(url).hostname or ""
                    if host and host in domains and plan.depth == "SURFACE":
                        continue
                    src = self._retrieve_url(
                        organisation_id,
                        research_id,
                        url,
                        sources_out,
                        evidence_out,
                        limitations,
                        domains,
                        urls_seen,
                        title_hint=hit.title,
                        snippet=hit.snippet,
                    )
                    if src and src.get("access_status") == "OK":
                        pages_retrieved += 1

            stop_reason = self.strategy.should_stop(
                sources_ok=sum(1 for s in sources_out if s.get("access_status") == "OK"),
                evidence_count=len(evidence_out),
                queries_used=queries_used,
                max_queries=plan.max_queries,
                contradictions=len(contradictions),
                depth=plan.depth,
            )
            if stop_reason:
                break

            # Gap → refine
            ok_sources = sum(1 for s in sources_out if s.get("access_status") == "OK")
            if ok_sources == 0 or (plan.depth in ("DEEP", "EXHAUSTIVE") and ok_sources < 2):
                gaps = ["primary evidence", "official source"] if ok_sources == 0 else ["additional corroboration"]
                extra = self.strategy.refine_after_gap(plan, gaps, used_queries)
                for eq in extra:
                    if eq not in pending_queries and eq not in used_queries:
                        pending_queries.append(eq)

        # Claims from evidence snippets
        for ev in evidence_out[:20]:
            text = (ev.get("extracted_text") or "")[:400]
            if not text.strip():
                continue
            claim_text = text.strip().split(". ")[0][:240]
            st = self.claims.record_claim(
                organisation_id,
                claim_text,
                research_id=research_id,
                supporting=[ev.get("evidence_id")] if ev.get("evidence_id") else [],
            )
            claims_out.append({
                "claim": claim_text,
                "status": st.get("status", "UNKNOWN"),
                "claim_id": st.get("claim_id"),
                "evidence_id": ev.get("evidence_id"),
                "source_id": ev.get("source_id"),
            })

        # Simple conflict: two OK sources with different titles treated as potential diversity, not auto-conflict
        ok = [s for s in sources_out if s.get("access_status") == "OK"]
        if len(ok) >= 2 and plan.depth in ("DEEP", "EXHAUSTIVE"):
            # record open conflict placeholder only when snippets disagree on a numeric pattern
            pass

        if not ok:
            unanswered.append(question)
            limitations.append("No pages successfully retrieved; findings empty")
            findings = []
        else:
            entities = []
            for s in ok[:5]:
                entities.extend(extract_entities(s.get("title") or ""))
            findings.append({
                "summary": f"Retrieved {len(ok)} source(s) across {len(domains)} domain(s) at depth {plan.depth}.",
                "source_count": len(ok),
                "domains": sorted(domains),
                "entities": entities[:15],
                "trust": "UNTRUSTED_EXTERNAL_CONTENT",
            })

        citations = build_citations(sources_out, evidence_out)
        result = {
            "research_id": research_id,
            "question": question,
            "depth": plan.depth,
            "status": "COMPLETED",
            "methodology": methodology,
            "sources": sources_out,
            "evidence": evidence_out,
            "claims": claims_out,
            "contradictions": contradictions,
            "findings": findings,
            "limitations": limitations,
            "unanswered_questions": unanswered,
            "citations": citations,
            "budget_used": {"queries": queries_used, "pages": pages_retrieved, "domains": len(domains)},
            "stop_reason": stop_reason or "completed",
            "search_logs": search_logs,
            "trust_policy": "UNTRUSTED_EXTERNAL_CONTENT",
            "courtroom_package": package_for_courtroom({
                "research_id": research_id,
                "question": question,
                "sources": sources_out,
                "evidence": evidence_out,
                "claims": claims_out,
                "contradictions": contradictions,
                "findings": findings,
                "citations": citations,
                "limitations": limitations,
                "methodology": methodology,
                "trust_policy": "UNTRUSTED_EXTERNAL_CONTENT",
            }),
        }

        with UnitOfWork() as uow:
            row = uow.session.get(InternetResearchCase, research_id)
            if row:
                row.status = "COMPLETED"
                row.findings = findings
                row.limitations = limitations
                row.unanswered = unanswered
                row.methodology = {**methodology, "stop_reason": result["stop_reason"]}
                row.budget_used = result["budget_used"]
                row.completed_at = datetime.utcnow()

        bus.publish(
            "internet.research.completed",
            {"research_id": research_id, "depth": plan.depth, "sources": len(sources_out)},
            organisation_id=organisation_id,
        )
        return result

    def _retrieve_url(
        self,
        organisation_id: str,
        research_id: str,
        url: str,
        sources_out: List[dict],
        evidence_out: List[dict],
        limitations: List[str],
        domains: Set[str],
        urls_seen: Set[str],
        title_hint: str = "",
        snippet: str = "",
    ) -> Optional[dict]:
        urls_seen.add(url)
        try:
            validate_url(url, UrlPolicy())
        except UrlSecurityError as e:
            src = self.sources.register(
                organisation_id,
                url,
                research_id=research_id,
                title=title_hint or url,
                access_status="BLOCKED_BY_POLICY",
                meta={"error": str(e)},
            )
            sources_out.append(src)
            limitations.append(f"BLOCKED_BY_POLICY: {url}")
            return src

        # Browser retrieve via external_fabric (mock or real provider)
        try:
            session = self.browser.create_session(
                organisation_id, agent_id="internet-orchestrator"
            )
            sid = session["session_id"]
            page = self.browser.navigate(sid, organisation_id, url)
            status = page.get("status") or "OK"
            if status in ("BLOCK", "REJECT"):
                access = "BLOCKED_BY_POLICY"
                title = title_hint or url
                text = ""
                content_hash = None
            elif status in ("FAILED", "ACCESS_FAILED", "ERROR", "CAPTCHA_DETECTED"):
                access = "ACCESS_FAILED" if status != "CAPTCHA_DETECTED" else "ACCESS_RESTRICTED"
                title = title_hint or url
                text = ""
                content_hash = None
            else:
                access = "OK"
                title = page.get("title") or title_hint or url
                text = page.get("text") or page.get("visible_text") or snippet or ""
                content_hash = page.get("content_hash")
                try:
                    obs = self.browser.observe(sid, organisation_id, url)
                    text = obs.get("visible_text") or obs.get("text") or text
                    content_hash = obs.get("content_hash") or content_hash
                    title = obs.get("title") or title
                except Exception:
                    pass
            host = urlparse(url).hostname or ""
            if host:
                domains.add(host)
            src = self.sources.register(
                organisation_id,
                url,
                research_id=research_id,
                title=title,
                access_status=access,
                content_hash=content_hash,
                meta={"provider": getattr(self.browser.provider, "name", "browser"), "nav_status": status},
            )
            sources_out.append(src)
            if src["access_status"] == "OK" and text:
                ev = self.evidence.add(
                    organisation_id,
                    research_id=research_id,
                    source_id=src["source_id"],
                    source_url=url,
                    extracted_text=text[:4000],
                    extraction_method="browser_extract",
                )
                evidence_out.append(ev)
            elif src["access_status"] != "OK":
                limitations.append(f"{src['access_status']}: {url}")
            try:
                self.browser.close(sid, organisation_id)
            except Exception:
                pass
            return src
        except Exception as e:
            src = self.sources.register(
                organisation_id,
                url,
                research_id=research_id,
                title=title_hint or url,
                access_status="ACCESS_FAILED",
                meta={"error": str(e)[:300]},
            )
            sources_out.append(src)
            limitations.append(f"ACCESS_FAILED: {url}")
            return src

    def get_research(self, organisation_id: str, research_id: str) -> dict:
        from core.errors import NotFoundError

        with UnitOfWork() as uow:
            row = uow.session.get(InternetResearchCase, research_id)
            if not row or row.organisation_id != organisation_id:
                raise NotFoundError(f"Research not found: {research_id}")
            return {
                "research_id": row.research_id,
                "organisation_id": row.organisation_id,
                "question": row.question,
                "depth": row.depth,
                "status": row.status,
                "methodology": row.methodology or {},
                "findings": row.findings or [],
                "limitations": row.limitations or [],
                "unanswered_questions": row.unanswered or [],
                "budget": row.budget or {},
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            }
