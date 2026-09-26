"""CINTEXA Business Intelligence API — FastAPI application."""

from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agents.registry import list_agents, get_agent, agent_ids
from config.settings import get_settings
from events.bus import bus
from orchestrator.core import Orchestrator
from orchestrator.workforce import workforce
from schemas.missions import MissionCreate, MissionPriority
from schemas.common import Priority, TaskState
from schemas.tasks import TaskCreate, Task
from reports.generator import generate_html_report, generate_json_report, generate_markdown_report


settings = get_settings()
orchestrator = Orchestrator()

from api.chat import ChatService, ChatRequest
from tools.llm import get_llm

chat_service = ChatService(orchestrator)


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

_cors = list(dict.fromkeys(settings.cors_origin_list + [
    "https://cintexa-business-intelligence-agent-workforce.pages.dev",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:4173",
    "http://localhost:3000",
    "http://localhost:8000",
]))
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors,
    allow_origin_regex=r"https://.*\.pages\.dev",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Simple auth dependency (replace with full JWT in production) ---
async def get_org_and_user(
    x_organisation_id: Optional[str] = Header(None, alias="X-Organisation-Id"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
) -> Dict[str, str]:
    return {
        "organisation_id": (x_organisation_id or "default-org").strip(),
        "user_id": (x_user_id or "default-user").strip(),
    }


async def get_llm_api_key(
    x_llm_api_key: Optional[str] = Header(None, alias="X-LLM-Api-Key"),
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    """Accept secret key from header only. Never log or echo the value."""
    if x_llm_api_key and x_llm_api_key.strip():
        return x_llm_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            return token
    return None


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


# --- Reports ---
class ReportRequest(BaseModel):
    task_id: Optional[str] = None
    mission_id: Optional[str] = None
    title: str = "CINTEXA Business Intelligence Report"
    report_type: str = "management"
    format: str = "markdown"  # markdown | html | json
    sections: Optional[Dict[str, Any]] = None


def _mission_report_sections(mission) -> Dict[str, Any]:
    """Build report sections from a completed Workforce Orchestrator mission.

    mission.result is a MissionResult pydantic model once synthesis has run
    (see WorkforceOrchestrator.synthesise -> mission.result = result in
    orchestrator/workforce.py), so it must be dumped to a dict rather than
    checked with isinstance(..., dict).
    """
    result = mission.result
    if result is not None and hasattr(result, "model_dump"):
        result = result.model_dump(mode="json")
    if isinstance(result, dict) and result:
        return result
    # Mission still running / no result yet — fall back to what we have.
    return {
        "executive_summary": f"Mission '{mission.objective}' is currently {mission.status.value}.",
        "objective": mission.objective,
        "status": mission.status.value,
    }


@app.post(f"{settings.api_prefix}/reports")
async def create_report(body: ReportRequest, auth: Dict = Depends(get_org_and_user)):
    sections = body.sections
    if sections is None:
        if body.task_id:
            task = orchestrator.get_task(body.task_id)
            if not task or task.organisation_id != auth["organisation_id"]:
                raise HTTPException(404, "Task not found")
            synthesis = task.results.get("synthesis") or {}
            sections = synthesis if isinstance(synthesis, dict) else {"executive_summary": str(synthesis)}
        elif body.mission_id:
            from orchestrator.workforce import workforce as wf
            mission = wf.get(body.mission_id)
            if not mission or mission.organisation_id != auth["organisation_id"]:
                raise HTTPException(404, "Mission not found")
            sections = _mission_report_sections(mission)
        else:
            raise HTTPException(
                400,
                "Provide 'task_id' (legacy task), 'mission_id' (Workforce Orchestrator mission), or 'sections'.",
            )

    fmt = (body.format or "markdown").lower()
    if fmt == "json":
        return generate_json_report(body.title, sections, body.report_type)
    if fmt == "html":
        html = generate_html_report(body.title, sections, body.report_type)
        return Response(content=html, media_type="text/html")
    markdown_report = generate_markdown_report(body.title, sections, body.report_type)
    return {
        "title": body.title,
        "report_type": body.report_type,
        "format": "markdown",
        "content": markdown_report,
    }


@app.get(f"{settings.api_prefix}/reports/{{task_id}}")
async def get_report_for_task(
    task_id: str,
    format: str = "markdown",
    auth: Dict = Depends(get_org_and_user),
):
    task = orchestrator.get_task(task_id)
    if not task or task.organisation_id != auth["organisation_id"]:
        raise HTTPException(404, "Task not found")
    synthesis = task.results.get("synthesis") or {}
    sections = synthesis if isinstance(synthesis, dict) else {"executive_summary": str(synthesis)}
    title = f"Business Intelligence Report — {task.objective or task.request}"

    fmt = (format or "markdown").lower()
    if fmt == "json":
        return generate_json_report(title, sections, "management")
    if fmt == "html":
        html = generate_html_report(title, sections, "management")
        return Response(content=html, media_type="text/html")
    return {
        "title": title,
        "format": "markdown",
        "content": generate_markdown_report(title, sections, "management"),
    }


# --- Events ---
@app.get(f"{settings.api_prefix}/events")
async def get_events(
    event_type: Optional[str] = None,
    limit: int = 50,
    auth: Dict = Depends(get_org_and_user),
):
    """Lifecycle event stream (diagnostic/research/competitor/QA started+completed,
    forecast.created, agent.failed) published on the internal event bus, scoped to
    the caller's organisation."""
    events = bus.history(event_type=event_type, limit=max(limit, 1) * 4)
    scoped = [e for e in events if e.get("organisation_id") == auth["organisation_id"]]
    return scoped[-limit:]


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


# --- Chat (GPT-style conversational interface) ---
@app.post(f"{settings.api_prefix}/chat")
async def chat(
    req: ChatRequest,
    auth: Dict = Depends(get_org_and_user),
    llm_api_key: Optional[str] = Depends(get_llm_api_key),
):
    try:
        return await chat_service.send(
            auth["organisation_id"],
            auth["user_id"],
            req,
            api_key=llm_api_key,
        )
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except Exception as e:
        # Never include secrets in error payloads
        raise HTTPException(500, "Chat failed. Check your API key in Settings and try again.")


@app.get(f"{settings.api_prefix}/chat/sessions")
async def list_chat_sessions(auth: Dict = Depends(get_org_and_user)):
    sessions = chat_service.list_sessions(auth["organisation_id"], auth["user_id"])
    return [s.model_dump() for s in sessions]


@app.get(f"{settings.api_prefix}/chat/sessions/{{session_id}}")
async def get_chat_session(session_id: str, auth: Dict = Depends(get_org_and_user)):
    session = chat_service.get_session(session_id)
    if not session or session.organisation_id != auth["organisation_id"]:
        raise HTTPException(404, "Session not found")
    return session.model_dump()


@app.post(f"{settings.api_prefix}/chat/sessions")
async def create_chat_session(auth: Dict = Depends(get_org_and_user)):
    session = chat_service.create_session(auth["organisation_id"], auth["user_id"])
    return session.model_dump()


# --- Health ---

# --- Workforce Orchestrator: Missions ---
class MissionCreateBody(BaseModel):
    objective: str
    priority: str = "NORMAL"
    context: Dict[str, Any] = Field(default_factory=dict)
    constraints: List[str] = Field(default_factory=list)
    deadline: Optional[str] = None
    success_criteria: List[str] = Field(default_factory=list)
    required_outputs: List[str] = Field(default_factory=list)
    approval_requirements: List[str] = Field(default_factory=list)
    idempotency_key: Optional[str] = None
    auto_run: bool = True


@app.post(f"{settings.api_prefix}/missions")
async def create_mission(
    body: MissionCreateBody,
    auth: Dict = Depends(get_org_and_user),
    llm_api_key: Optional[str] = Header(None, alias="X-LLM-Api-Key"),
):
    from orchestrator.workforce import workforce as wf
    try:
        pr = MissionPriority[body.priority] if body.priority in MissionPriority.__members__ else MissionPriority.NORMAL
    except Exception:
        pr = MissionPriority.NORMAL
    payload = MissionCreate(
        objective=body.objective,
        organisation_id=auth["organisation_id"],
        user_id=auth["user_id"],
        priority=pr,
        context=body.context,
        constraints=body.constraints,
        deadline=body.deadline,
        success_criteria=body.success_criteria,
        required_outputs=body.required_outputs,
        approval_requirements=body.approval_requirements,
        idempotency_key=body.idempotency_key,
    )
    key = None
    # Header may be injected via Depends pattern elsewhere — read raw if needed
    mission = await wf.create_and_run(payload, api_key=llm_api_key, auto_run=body.auto_run)
    return mission.model_dump()


@app.get(f"{settings.api_prefix}/missions/{{mission_id}}")
async def get_mission(mission_id: str, auth: Dict = Depends(get_org_and_user)):
    from orchestrator.workforce import workforce as wf
    m = wf.get(mission_id)
    if not m or m.organisation_id != auth["organisation_id"]:
        raise HTTPException(404, "Mission not found")
    return m.model_dump()


@app.post(f"{settings.api_prefix}/missions/{{mission_id}}/cancel")
async def cancel_mission(mission_id: str, auth: Dict = Depends(get_org_and_user)):
    from orchestrator.workforce import workforce as wf
    m = wf.get(mission_id)
    if not m or m.organisation_id != auth["organisation_id"]:
        raise HTTPException(404, "Mission not found")
    m = await wf.cancel(mission_id)
    return m.model_dump()


@app.post(f"{settings.api_prefix}/missions/{{mission_id}}/pause")
async def pause_mission(mission_id: str, auth: Dict = Depends(get_org_and_user)):
    from orchestrator.workforce import workforce as wf
    m = wf.get(mission_id)
    if not m or m.organisation_id != auth["organisation_id"]:
        raise HTTPException(404, "Mission not found")
    return (await wf.pause(mission_id)).model_dump()


@app.post(f"{settings.api_prefix}/missions/{{mission_id}}/resume")
async def resume_mission(
    mission_id: str,
    auth: Dict = Depends(get_org_and_user),
    llm_api_key: Optional[str] = Header(None, alias="X-LLM-Api-Key"),
):
    from orchestrator.workforce import workforce as wf
    m = wf.get(mission_id)
    if not m or m.organisation_id != auth["organisation_id"]:
        raise HTTPException(404, "Mission not found")
    return (await wf.resume(mission_id, api_key=llm_api_key)).model_dump()


@app.post(f"{settings.api_prefix}/missions/{{mission_id}}/approve")
async def approve_mission(
    mission_id: str,
    auth: Dict = Depends(get_org_and_user),
    llm_api_key: Optional[str] = Header(None, alias="X-LLM-Api-Key"),
):
    from orchestrator.workforce import workforce as wf
    m = wf.get(mission_id)
    if not m or m.organisation_id != auth["organisation_id"]:
        raise HTTPException(404, "Mission not found")
    return (await wf.approve(mission_id, api_key=llm_api_key)).model_dump()


@app.post(f"{settings.api_prefix}/missions/{{mission_id}}/replan")
async def replan_mission(
    mission_id: str,
    auth: Dict = Depends(get_org_and_user),
    llm_api_key: Optional[str] = Header(None, alias="X-LLM-Api-Key"),
):
    from orchestrator.workforce import workforce as wf
    m = wf.get(mission_id)
    if not m or m.organisation_id != auth["organisation_id"]:
        raise HTTPException(404, "Mission not found")
    return (await wf.replan(mission_id, api_key=llm_api_key)).model_dump()


@app.get(f"{settings.api_prefix}/missions/{{mission_id}}/plan")
async def mission_plan(mission_id: str, auth: Dict = Depends(get_org_and_user)):
    from orchestrator.workforce import workforce as wf
    m = wf.get(mission_id)
    if not m or m.organisation_id != auth["organisation_id"]:
        raise HTTPException(404, "Mission not found")
    return m.plan.model_dump() if m.plan else {}


@app.get(f"{settings.api_prefix}/missions/{{mission_id}}/tasks")
async def mission_tasks(mission_id: str, auth: Dict = Depends(get_org_and_user)):
    from orchestrator.workforce import workforce as wf
    m = wf.get(mission_id)
    if not m or m.organisation_id != auth["organisation_id"]:
        raise HTTPException(404, "Mission not found")
    return [t.model_dump() for t in m.tasks]


@app.get(f"{settings.api_prefix}/missions/{{mission_id}}/agents")
async def mission_agents(mission_id: str, auth: Dict = Depends(get_org_and_user)):
    from orchestrator.workforce import workforce as wf
    m = wf.get(mission_id)
    if not m or m.organisation_id != auth["organisation_id"]:
        raise HTTPException(404, "Mission not found")
    return {"team": m.assigned_agents}


@app.get(f"{settings.api_prefix}/missions/{{mission_id}}/evidence")
async def mission_evidence(mission_id: str, auth: Dict = Depends(get_org_and_user)):
    from orchestrator.workforce import workforce as wf
    m = wf.get(mission_id)
    if not m or m.organisation_id != auth["organisation_id"]:
        raise HTTPException(404, "Mission not found")
    return m.evidence


@app.get(f"{settings.api_prefix}/missions/{{mission_id}}/conflicts")
async def mission_conflicts(mission_id: str, auth: Dict = Depends(get_org_and_user)):
    from orchestrator.workforce import workforce as wf
    m = wf.get(mission_id)
    if not m or m.organisation_id != auth["organisation_id"]:
        raise HTTPException(404, "Mission not found")
    return [c.model_dump() for c in m.conflicts]


@app.get(f"{settings.api_prefix}/missions/{{mission_id}}/events")
async def mission_events(mission_id: str, auth: Dict = Depends(get_org_and_user)):
    from orchestrator.workforce import workforce as wf
    m = wf.get(mission_id)
    if not m or m.organisation_id != auth["organisation_id"]:
        raise HTTPException(404, "Mission not found")
    return m.events


@app.get(f"{settings.api_prefix}/missions/{{mission_id}}/trace")
async def mission_trace(mission_id: str, auth: Dict = Depends(get_org_and_user)):
    from orchestrator.workforce import workforce as wf
    m = wf.get(mission_id)
    if not m or m.organisation_id != auth["organisation_id"]:
        raise HTTPException(404, "Mission not found")
    return wf.trace(mission_id)


@app.get(f"{settings.api_prefix}/missions/{{mission_id}}/metrics")
async def mission_metrics(mission_id: str, auth: Dict = Depends(get_org_and_user)):
    from orchestrator.workforce import workforce as wf
    m = wf.get(mission_id)
    if not m or m.organisation_id != auth["organisation_id"]:
        raise HTTPException(404, "Mission not found")
    return {
        "execution_metrics": m.execution_metrics,
        "confidence": m.confidence,
        "quality_score": m.quality_score,
        "status": m.status.value,
    }


@app.get(f"{settings.api_prefix}/missions/{{mission_id}}/report")
async def mission_report(
    mission_id: str,
    format: str = "markdown",
    auth: Dict = Depends(get_org_and_user),
):
    """Generate a report (markdown | html | json) directly from a mission's result."""
    from orchestrator.workforce import workforce as wf
    mission = wf.get(mission_id)
    if not mission or mission.organisation_id != auth["organisation_id"]:
        raise HTTPException(404, "Mission not found")
    sections = _mission_report_sections(mission)
    title = f"Business Intelligence Report — {mission.objective}"

    fmt = (format or "markdown").lower()
    if fmt == "json":
        return generate_json_report(title, sections, "management")
    if fmt == "html":
        html = generate_html_report(title, sections, "management")
        return Response(content=html, media_type="text/html")
    return {
        "title": title,
        "format": "markdown",
        "content": generate_markdown_report(title, sections, "management"),
    }




@app.get(f"{settings.api_prefix}/missions/{{mission_id}}/stream")
async def mission_event_stream(mission_id: str, auth: Dict = Depends(get_org_and_user)):
    """Server-Sent Events stream of mission progress (polling snapshot)."""
    from fastapi.responses import StreamingResponse
    from orchestrator.workforce import workforce as wf
    import asyncio, json

    m = wf.get(mission_id)
    if not m or m.organisation_id != auth["organisation_id"]:
        raise HTTPException(404, "Mission not found")

    async def gen():
        last = 0
        for _ in range(120):  # ~2 minutes at 1s
            mission = wf.get(mission_id)
            if not mission:
                break
            events = mission.events[last:]
            for ev in events:
                yield f"data: {json.dumps(ev)}\n\n"
            last = len(mission.events)
            if mission.status.value in ("COMPLETED", "FAILED", "CANCELLED"):
                end_payload = {"event_type": "stream.end", "status": mission.status.value}
                yield f"data: {json.dumps(end_payload)}\n\n"
                break
            await asyncio.sleep(1)

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get(f"{settings.api_prefix}/orchestrator/metrics")
async def orchestrator_metrics_endpoint():
    from orchestrator.metrics import orchestrator_metrics
    return orchestrator_metrics.snapshot()


@app.get("/health")
async def health():
    llm = get_llm()
    server_key = bool(settings.openai_api_key or settings.anthropic_api_key)
    return {
        "status": "ok",
        "service": settings.app_name,
        "agents": agent_ids(),
        "server_llm_configured": server_key,
        "chat": True,
    }


@app.get("/")
async def root():
    """Serve the chat UI when available; otherwise JSON status."""
    index = Path(__file__).resolve().parent.parent / "index.html"
    if index.is_file():
        return FileResponse(index)
    return {
        "message": "CINTEXA Business Intelligence Agent Workforce",
        "docs": "/docs",
        "api_prefix": settings.api_prefix,
        "chat": f"{settings.api_prefix}/chat",
    }


@app.get("/api")
async def api_info():
    return {
        "message": "CINTEXA Business Intelligence Agent Workforce",
        "docs": "/docs",
        "api_prefix": settings.api_prefix,
        "chat": f"POST {settings.api_prefix}/chat",
        "health": "/health",
    }


# --- Static UI (same origin — no API base URL required in the browser) ---
_ROOT = Path(__file__).resolve().parent.parent
_ASSETS = _ROOT / "assets"
if _ASSETS.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_ASSETS)), name="assets")


@app.get("/app")
@app.get("/chat")
async def spa_app():
    index = _ROOT / "index.html"
    if index.is_file():
        return FileResponse(index)
    raise HTTPException(404, "UI not found")


# Prefer serving the chat UI at / when Accept is HTML; JSON clients still get the API root via explicit Accept
@app.get("/ui")
async def spa_ui():
    index = _ROOT / "index.html"
    if index.is_file():
        return FileResponse(index)
    raise HTTPException(404, "UI not found")


@app.get("/dashboard")
async def spa_dashboard():
    """Serve the executive workspace dashboard (agents, tasks, diagnostics, forecasts, reports)."""
    page = _ROOT / "dashboard.html"
    if page.is_file():
        return FileResponse(page)
    raise HTTPException(404, "Dashboard not found")

