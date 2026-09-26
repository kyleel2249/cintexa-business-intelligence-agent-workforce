"""Web research with provenance — never fabricates access."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Set

from events.bus import bus
from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from external_fabric.browser import BrowserEngine
from external_fabric.models_db import ExtResearchSession
from external_fabric.url_security import UrlPolicy, validate_url, UrlSecurityError


class WebResearchEngine:
    def __init__(self, browser: Optional[BrowserEngine] = None):
        self.browser = browser or BrowserEngine()

    def research(
        self,
        organisation_id: str,
        query: str,
        seed_urls: List[str],
        *,
        permissions: Optional[Set[str]] = None,
        max_pages: int = 5,
    ) -> dict:
        rid = new_id("RES-")
        with UnitOfWork() as uow:
            uow.session.add(
                ExtResearchSession(
                    research_id=rid,
                    organisation_id=organisation_id,
                    query=query,
                    status="RUNNING",
                    sources=[],
                    findings=[],
                )
            )
        bus.publish("research.started", {"research_id": rid, "query": query}, organisation_id=organisation_id)

        sess = self.browser.create_session(organisation_id, allowed_domains=None)
        sources = []
        findings = []
        for url in seed_urls[:max_pages]:
            try:
                validate_url(url, UrlPolicy())
            except UrlSecurityError as e:
                sources.append({"url": url, "status": "ACCESS_FAILED", "error": str(e)})
                continue
            try:
                self.browser.navigate(sess["session_id"], organisation_id, url, permissions=permissions or {"*"})
                obs = self.browser.observe(sess["session_id"], organisation_id, url)
                sources.append(
                    {
                        "url": url,
                        "status": "OK",
                        "title": obs.get("title"),
                        "content_hash": obs.get("content_hash"),
                        "retrieved_at": datetime.utcnow().isoformat(),
                        "trust": "EXTERNAL_UNTRUSTED",
                    }
                )
                text = obs.get("visible_text") or ""
                if query.lower().split()[0] in text.lower() or True:
                    findings.append(
                        {
                            "source_url": url,
                            "excerpt": text[:500],
                            "claim_type": "observation",
                            "confidence": "unverified",
                        }
                    )
            except Exception as e:
                sources.append({"url": url, "status": "ACCESS_FAILED", "error": str(e)[:300]})

        self.browser.close(sess["session_id"], organisation_id)
        with UnitOfWork() as uow:
            row = uow.session.get(ExtResearchSession, rid)
            if row:
                row.sources = sources
                row.findings = findings
                row.status = "COMPLETED"
                row.completed_at = datetime.utcnow()
        bus.publish("research.completed", {"research_id": rid}, organisation_id=organisation_id)
        return {
            "research_id": rid,
            "status": "COMPLETED",
            "sources": sources,
            "findings": findings,
            "query": query,
        }
