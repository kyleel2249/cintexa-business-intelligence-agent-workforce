"""Source registry and quality classification."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from internet_fabric.models_db import InternetSource


OFFICIAL_HINTS = ("gov", "edu", "w3.org", "ietf.org", "rfc-editor.org", "example.com")
TECH_HINTS = ("docs.", "developer.", "api.", "rfc", "spec")
NEWS_HINTS = ("news", "times", "post", "reuters", "bbc")


class SourceQualityEngine:
    def classify(self, url: str, meta: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        meta = meta or {}
        if meta.get("category"):
            return {"source_category": meta["category"], "reliability": "MEDIUM"}
        host = (urlparse(url).hostname or "").lower()
        if any(h in host for h in OFFICIAL_HINTS) or host.endswith(".gov") or host.endswith(".edu"):
            return {"source_category": "OFFICIAL_SOURCE", "reliability": "HIGH"}
        if any(h in host for h in TECH_HINTS):
            return {"source_category": "TECHNICAL_DOCUMENTATION", "reliability": "MEDIUM"}
        if any(h in host for h in NEWS_HINTS):
            return {"source_category": "NEWS_SOURCE", "reliability": "MEDIUM"}
        return {"source_category": "UNKNOWN", "reliability": "UNKNOWN"}


class SourceRegistry:
    def __init__(self):
        self.quality = SourceQualityEngine()

    def register(
        self,
        organisation_id: str,
        url: str,
        *,
        research_id: Optional[str] = None,
        title: str = "",
        access_status: str = "OK",
        content_hash: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> dict:
        meta = meta or {}
        q = self.quality.classify(url, meta)
        domain = urlparse(url).hostname or ""
        sid = new_id("SRC-")
        with UnitOfWork() as uow:
            uow.session.add(
                InternetSource(
                    source_id=sid,
                    organisation_id=organisation_id,
                    research_id=research_id,
                    url=url,
                    domain=domain,
                    title=title,
                    source_category=q["source_category"],
                    reliability=q["reliability"],
                    content_hash=content_hash,
                    retrieved_at=datetime.utcnow() if access_status == "OK" else None,
                    access_status=access_status,
                    meta=meta,
                    trust="UNTRUSTED_EXTERNAL_CONTENT",
                )
            )
        return {
            "source_id": sid,
            "url": url,
            "domain": domain,
            "title": title,
            "source_category": q["source_category"],
            "reliability": q["reliability"],
            "access_status": access_status,
            "trust": "UNTRUSTED_EXTERNAL_CONTENT",
        }

    def list_for_research(self, organisation_id: str, research_id: str) -> List[dict]:
        with UnitOfWork() as uow:
            rows = (
                uow.session.query(InternetSource)
                .filter_by(organisation_id=organisation_id, research_id=research_id)
                .all()
            )
            return [
                {
                    "source_id": r.source_id,
                    "url": r.url,
                    "title": r.title,
                    "source_category": r.source_category,
                    "reliability": r.reliability,
                    "access_status": r.access_status,
                    "trust": r.trust,
                    "retrieved_at": r.retrieved_at.isoformat() if r.retrieved_at else None,
                }
                for r in rows
            ]
