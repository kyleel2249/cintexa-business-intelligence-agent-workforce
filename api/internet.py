"""Internet Intelligence API routes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from internet_fabric.orchestrator import InternetResearchOrchestrator
from internet_fabric.search import SearchFabric
from internet_fabric.capabilities import list_capabilities
from internet_fabric.api_registry import default_api_registry, ExternalAPI
from internet_fabric.courtroom_adapter import NullCourtroomSink, package_for_courtroom
from internet_fabric.strategy import SearchStrategyEngine
from core.errors import NotFoundError, ValidationError

router = APIRouter(prefix="/internet", tags=["internet"])


def _org(x_org_id: Optional[str]) -> str:
    return x_org_id or "default"


class SearchBody(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    max_results: int = Field(10, ge=1, le=50)


class ResearchBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    depth: str = Field("STANDARD", pattern="^(SURFACE|STANDARD|DEEP|EXHAUSTIVE)$")
    seed_urls: List[str] = Field(default_factory=list)
    budget: Dict[str, Any] = Field(default_factory=dict)
    agent_id: Optional[str] = None
    case_id: Optional[str] = None


class PlanBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    depth: str = Field("STANDARD")
    budget: Dict[str, Any] = Field(default_factory=dict)


class APIRegisterBody(BaseModel):
    api_id: str
    name: str
    base_url: str
    endpoints: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


@router.get("/capabilities")
def capabilities(risk: Optional[str] = None):
    return {"capabilities": list_capabilities(risk=risk), "count": len(list_capabilities(risk=risk))}


@router.post("/plan")
def plan_research(body: PlanBody):
    plan = SearchStrategyEngine().plan(body.question, depth=body.depth, budget=body.budget)
    return {
        "depth": plan.depth,
        "primary": plan.primary,
        "families": [{"name": f.name, "query": f.query, "purpose": f.purpose} for f in plan.families],
        "max_queries": plan.max_queries,
        "max_pages": plan.max_pages,
    }


@router.post("/search")
def search(body: SearchBody, x_org_id: Optional[str] = Header(default=None, alias="X-Org-Id")):
    org = _org(x_org_id)
    result = SearchFabric().search(org, body.query, max_results=body.max_results)
    return {
        "query": result.query,
        "status": result.status,
        "hits": [
            {"title": h.title, "url": h.url, "snippet": h.snippet, "score": h.score, "source_name": h.source_name}
            for h in result.hits
        ],
        "providers_tried": result.providers_tried,
        "fallback_used": result.fallback_used,
        "latency_ms": result.latency_ms,
        "logs": result.logs,
    }


@router.post("/research")
def research(body: ResearchBody, x_org_id: Optional[str] = Header(default=None, alias="X-Org-Id")):
    org = _org(x_org_id)
    orch = InternetResearchOrchestrator()
    return orch.research(
        org,
        body.question,
        depth=body.depth,
        seed_urls=body.seed_urls,
        budget=body.budget,
        agent_id=body.agent_id,
        case_id=body.case_id,
    )


@router.get("/research/{research_id}")
def get_research(research_id: str, x_org_id: Optional[str] = Header(default=None, alias="X-Org-Id")):
    org = _org(x_org_id)
    try:
        return InternetResearchOrchestrator().get_research(org, research_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/research/{research_id}/sources")
def research_sources(research_id: str, x_org_id: Optional[str] = Header(default=None, alias="X-Org-Id")):
    org = _org(x_org_id)
    try:
        case = InternetResearchOrchestrator().get_research(org, research_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    # Sources live in registry tables; return case metadata + note
    return {"research_id": research_id, "status": case["status"], "methodology": case.get("methodology")}


@router.post("/apis/register")
def register_api(body: APIRegisterBody, x_org_id: Optional[str] = Header(default=None, alias="X-Org-Id")):
    org = _org(x_org_id)
    try:
        api = default_api_registry.register(
            ExternalAPI(
                api_id=body.api_id,
                name=body.name,
                base_url=body.base_url,
                organisation_id=org,
                endpoints=body.endpoints or {"default": {}},
            )
        )
        return {"api_id": api.api_id, "enabled": api.enabled}
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/apis")
def list_apis(x_org_id: Optional[str] = Header(default=None, alias="X-Org-Id")):
    return {"apis": default_api_registry.list_for_org(_org(x_org_id))}


@router.post("/courtroom/package/{research_id}")
def courtroom_package(research_id: str, x_org_id: Optional[str] = Header(default=None, alias="X-Org-Id")):
    org = _org(x_org_id)
    try:
        case = InternetResearchOrchestrator().get_research(org, research_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    # Minimal package from durable case (full package produced at research time)
    pkg = package_for_courtroom({
        "research_id": case["research_id"],
        "question": case["question"],
        "findings": case.get("findings") or [],
        "limitations": case.get("limitations") or [],
        "methodology": case.get("methodology"),
        "trust_policy": "UNTRUSTED_EXTERNAL_CONTENT",
    })
    sink = NullCourtroomSink()
    delivery = sink.accept_internet_evidence(case_id=research_id, organisation_id=org, research_result=pkg)
    return {"package": pkg, "delivery": delivery}
