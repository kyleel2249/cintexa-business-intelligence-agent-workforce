"""Internet Intelligence API routes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from internet_fabric.orchestrator import InternetResearchOrchestrator
from internet_fabric.search import SearchFabric
from internet_fabric.capabilities import list_capabilities

router = APIRouter(prefix="/internet", tags=["internet"])


def _org(x_org_id: Optional[str]) -> str:
    return x_org_id or "default"


class SearchBody(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    max_results: int = Field(10, ge=1, le=50)


class ResearchBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    depth: str = Field("STANDARD", pattern="^(SURFACE|STANDARD|DEEP|EXHAUSTIVE)$")
    seed_urls: Optional[List[str]] = None
    budget: Optional[Dict[str, int]] = None


@router.get("/capabilities")
def capabilities():
    return {"capabilities": list_capabilities()}


@router.post("/search")
def search(body: SearchBody, x_org_id: Optional[str] = Header(None, alias="X-Org-Id")):
    org = _org(x_org_id)
    result = SearchFabric().search(org, body.query, max_results=body.max_results)
    return {
        "query": result.query,
        "status": result.status,
        "hits": [
            {
                "title": h.title,
                "url": h.url,
                "snippet": h.snippet,
                "score": h.score,
                "meta": h.meta,
            }
            for h in result.hits
        ],
        "providers_tried": result.providers_tried,
        "fallback_used": result.fallback_used,
        "latency_ms": result.latency_ms,
        "logs": result.logs,
    }


@router.post("/research")
def research(body: ResearchBody, x_org_id: Optional[str] = Header(None, alias="X-Org-Id")):
    org = _org(x_org_id)
    try:
        out = InternetResearchOrchestrator().research(
            org,
            body.question,
            depth=body.depth,
            seed_urls=body.seed_urls,
            budget=body.budget,
        )
        return out
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)[:500]) from exc


@router.get("/research/{research_id}")
def get_research(research_id: str, x_org_id: Optional[str] = Header(None, alias="X-Org-Id")):
    org = _org(x_org_id)
    try:
        return InternetResearchOrchestrator().get_research(org, research_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)[:300]) from exc
