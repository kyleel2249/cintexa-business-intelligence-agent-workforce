"""CINTEXA Business Intelligence API — FastAPI application."""

from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agents.registry import list_agents, get_agent, agent_ids
from config.settings import get_settings
from orchestrator.core import Orchestrator
from schemas.common import Priority, TaskState
from schemas.tasks import TaskCreate, Task


settings = get_settings()
orchestrator = Orchestrator()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: agents are lazy-loaded by orchestrator
    yield
    # Shutdown hooks if needed


app = FastAPI(
    title=settings.app_name,
    description="CINTEXA Business Intelligence Agent Workforce API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Simple auth dependency (replace with full JWT in production) ---
async def get_org_and_user(
    x_organisation_id: str = Header(..., alias="X-Organisation-Id"),
    x_user_id: str = Header(..., alias="X-User-Id"),
) -> Dict[str, str]:
    if not x_organisation_id or not x_user_id:
        raise HTTPException(401, "Organisation and user headers required")
    return {"organisation_id": x_organisation_id, "user_id": x_user_id}


# --- Tasks ---
@app.post(f"{settings.api_prefix}/tasks", response_model=Dict[str, Any])
async def create_task(payload: TaskCreate, auth: Dict = Depends(get_org_and_user)):
    payload.organisation_id = auth["organisation_id"]
    payload.user_id = auth["user_id"]
    task = orchestrator.create_task(payload)
    # Optionally auto-run
    task = await orchestrator.run(task.task_id)
    return task.model_dump()


@app.get(f"{settings.api_prefix}/tasks/{{task_id}}")
async def get_task(task_id: str, auth: Dict = Depends(get_org_and_user)):
    task = orchestrator.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task.organisation_id != auth["organisation_id"]:
        raise HTTPException(403, "Organisation isolation violation")
    return task.model_dump()


@app.post(f"{settings.api_prefix}/tasks/{{task_id}}/cancel")
async def cancel_task(task_id: str, auth: Dict = Depends(get_org_and_user)):
    task = orchestrator.get_task(task_id)
    if not task or task.organisation_id != auth["organisation_id"]:
        raise HTTPException(404, "Task not found")
    task = orchestrator.cancel_task(task_id)
    return task.model_dump()


@app.post(f"{settings.api_prefix}/tasks/{{task_id}}/resume")
async def resume_task(task_id: str, auth: Dict = Depends(get_org_and_user)):
    task = orchestrator.get_task(task_id)
    if not task or task.organisation_id != auth["organisation_id"]:
        raise HTTPException(404, "Task not found")
    task = orchestrator.resume_task(task_id)
    task = await orchestrator.run(task_id)
    return task.model_dump()


# --- Diagnostics ---
class DiagnosticRequest(BaseModel):
    metrics: Dict[str, Any] = Field(default_factory=dict)
    answers: Dict[str, Any] = Field(default_factory=dict)
    business_profile_id: Optional[str] = None


@app.post(f"{settings.api_prefix}/diagnostics")
async def run_diagnostic(body: DiagnosticRequest, auth: Dict = Depends(get_org_and_user)):
    payload = TaskCreate(
        request="Assess my business health",
        organisation_id=auth["organisation_id"],
        user_id=auth["user_id"],
        priority=Priority.HIGH,
        context={"metrics": body.metrics, "answers": body.answers},
        business_profile_id=body.business_profile_id,
    )
    task = orchestrator.create_task(payload)
    task = await orchestrator.run(task.task_id)
    return {
        "task_id": task.task_id,
        "state": task.state.value,
        "diagnostic": task.results.get("diagnostic"),
        "qa": task.results.get("quality"),
        "synthesis": task.results.get("synthesis"),
    }


# --- Research ---
class ResearchRequest(BaseModel):
    question: str
    industry: Optional[str] = None
    geography: Optional[str] = None
    tool_results: Optional[List[Dict[str, Any]]] = None


@app.post(f"{settings.api_prefix}/research")
async def run_research(body: ResearchRequest, auth: Dict = Depends(get_org_and_user)):
    payload = TaskCreate(
        request=body.question,
        organisation_id=auth["organisation_id"],
        user_id=auth["user_id"],
        context={
            "industry": body.industry,
            "geography": body.geography,
            "tool_results": body.tool_results or [],
        },
    )
    task = orchestrator.create_task(payload)
    task = await orchestrator.run(task.task_id)
    return {
        "task_id": task.task_id,
        "state": task.state.value,
        "research": task.results.get("research"),
        "market": task.results.get("market"),
        "qa": task.results.get("quality"),
    }


# --- Forecasts ---
class ForecastRequest(BaseModel):
    metric: str = "revenue"
    historical_series: Dict[str, List[float]]
    horizon_months: int = 12


@app.post(f"{settings.api_prefix}/forecasts")
async def run_forecast(body: ForecastRequest, auth: Dict = Depends(get_org_and_user)):
    payload = TaskCreate(
        request=f"Forecast {body.metric} for next {body.horizon_months} months",
        organisation_id=auth["organisation_id"],
        user_id=auth["user_id"],
        context={
            "historical_series": body.historical_series,
            "horizon_months": body.horizon_months,
            "metric": body.metric,
        },
    )
    task = orchestrator.create_task(payload)
    task = await orchestrator.run(task.task_id)
    return {
        "task_id": task.task_id,
        "state": task.state.value,
        "forecasting": task.results.get("forecasting"),
        "qa": task.results.get("quality"),
    }


# --- Competitors ---
class CompetitorRequest(BaseModel):
    competitors: List[str]
    industry: Optional[str] = None
    tool_results: Optional[List[Dict[str, Any]]] = None


@app.post(f"{settings.api_prefix}/competitors/research")
async def competitor_research(body: CompetitorRequest, auth: Dict = Depends(get_org_and_user)):
    payload = TaskCreate(
        request=f"Research competitors: {', '.join(body.competitors)}",
        organisation_id=auth["organisation_id"],
        user_id=auth["user_id"],
        context={
            "competitors": body.competitors,
            "industry": body.industry,
            "tool_results": body.tool_results or [],
        },
    )
    task = orchestrator.create_task(payload)
    task = await orchestrator.run(task.task_id)
    return {
        "task_id": task.task_id,
        "state": task.state.value,
        "competitor": task.results.get("competitor"),
        "research": task.results.get("research"),
        "qa": task.results.get("quality"),
    }


# --- Decision support ---
class DecisionRequest(BaseModel):
    decision: str
    options: Optional[List[Any]] = None
    objectives: Optional[List[str]] = None
    constraints: Optional[List[str]] = None


@app.post(f"{settings.api_prefix}/decisions/analyze")
async def analyse_decision(body: DecisionRequest, auth: Dict = Depends(get_org_and_user)):
    payload = TaskCreate(
        request=body.decision,
        organisation_id=auth["organisation_id"],
        user_id=auth["user_id"],
        context={
            "decision": body.decision,
            "options": body.options or [],
            "objectives": body.objectives or [],
            "constraints": body.constraints or [],
        },
    )
    task = orchestrator.create_task(payload)
    task = await orchestrator.run(task.task_id)
    return {
        "task_id": task.task_id,
        "state": task.state.value,
        "decision": task.results.get("decision"),
        "qa": task.results.get("quality"),
    }


# --- Dashboard ---
@app.get(f"{settings.api_prefix}/dashboard")
async def dashboard(auth: Dict = Depends(get_org_and_user)):
    agents = [a.model_dump() for a in list_agents()]
    # In production aggregate from DB
    return {
        "organisation_id": auth["organisation_id"],
        "overview": {
            "business_health_score": None,
            "note": "Run a diagnostic to populate health score",
            "active_agents": [a["agent_id"] for a in agents if a.get("enabled")],
        },
        "agents": agents,
        "recent_tasks": [
            t.model_dump()
            for t in orchestrator._tasks.values()
            if t.organisation_id == auth["organisation_id"]
        ][-10:],
    }


# --- Agents ---
@app.get(f"{settings.api_prefix}/agents")
async def get_agents():
    return [a.model_dump() for a in list_agents(enabled_only=False)]


@app.get(f"{settings.api_prefix}/agents/{{agent_id}}")
async def get_agent_detail(agent_id: str):
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent.model_dump()


@app.get(f"{settings.api_prefix}/agents/{{agent_id}}/activity")
async def agent_activity(agent_id: str, auth: Dict = Depends(get_org_and_user)):
    # Placeholder — production reads from agent_runs table
    return {
        "agent_id": agent_id,
        "organisation_id": auth["organisation_id"],
        "activity": [],
        "note": "Activity log populated when runs are persisted to the database.",
    }


# --- Health ---
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": settings.app_name,
        "agents": agent_ids(),
    }


@app.get("/")
async def root():
    return {
        "message": "CINTEXA Business Intelligence Agent Workforce",
        "docs": "/docs",
        "api_prefix": settings.api_prefix,
    }
