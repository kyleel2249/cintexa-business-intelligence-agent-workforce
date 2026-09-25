"""Chat service — conversation sessions backed by the BI orchestrator + LLM."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from orchestrator.core import Orchestrator
from schemas.common import Priority
from schemas.tasks import TaskCreate
from tools.llm import get_llm


class ChatMessage(BaseModel):
    role: str  # user | assistant | system
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat() + "Z")
    task_id: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class ChatSession(BaseModel):
    session_id: str
    organisation_id: str
    user_id: str
    title: str = "New chat"
    messages: List[ChatMessage] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat() + "Z")
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat() + "Z")


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    # Optional structured data for specialists
    metrics: Optional[Dict[str, Any]] = None
    historical_series: Optional[Dict[str, List[float]]] = None
    industry: Optional[str] = None
    geography: Optional[str] = None
    competitors: Optional[List[str]] = None


class ChatService:
    def __init__(self, orchestrator: Orchestrator):
        self.orchestrator = orchestrator
        self._sessions: Dict[str, ChatSession] = {}
        self.llm = get_llm()

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        return self._sessions.get(session_id)

    def list_sessions(self, organisation_id: str, user_id: str) -> List[ChatSession]:
        return [
            s
            for s in self._sessions.values()
            if s.organisation_id == organisation_id and s.user_id == user_id
        ]

    def create_session(self, organisation_id: str, user_id: str, title: str = "New chat") -> ChatSession:
        sid = f"CHAT-{uuid.uuid4()}"
        session = ChatSession(
            session_id=sid,
            organisation_id=organisation_id,
            user_id=user_id,
            title=title,
        )
        self._sessions[sid] = session
        return session

    async def send(self, organisation_id: str, user_id: str, req: ChatRequest, api_key: Optional[str] = None) -> Dict[str, Any]:
        # Session
        if req.session_id and req.session_id in self._sessions:
            session = self._sessions[req.session_id]
            if session.organisation_id != organisation_id:
                raise PermissionError("Organisation isolation violation")
        else:
            title = (req.message[:48] + "…") if len(req.message) > 48 else req.message
            session = self.create_session(organisation_id, user_id, title=title or "New chat")

        user_msg = ChatMessage(role="user", content=req.message)
        session.messages.append(user_msg)

        # Build context for orchestrator
        context: Dict[str, Any] = dict(req.context or {})
        if req.metrics:
            context["metrics"] = req.metrics
        if req.historical_series:
            context["historical_series"] = req.historical_series
        if req.industry:
            context["industry"] = req.industry
        if req.geography:
            context["geography"] = req.geography
        if req.competitors:
            context["competitors"] = req.competitors

        # Optional LLM plan refinement
        history = [{"role": m.role, "content": m.content} for m in session.messages[-8:] if m.role in ("user", "assistant")]
        plan_hint = self.llm.plan_objective(req.message, history[:-1] if history else None, api_key=api_key)

        payload = TaskCreate(
            request=req.message,
            organisation_id=organisation_id,
            user_id=user_id,
            priority=Priority.HIGH,
            context=context,
        )
        task = self.orchestrator.create_task(payload)

        # If LLM suggested agents, merge into plan
        if plan_hint.get("agents") and task.plan:
            suggested = [a for a in plan_hint["agents"] if a in (
                "strategy", "intelligence", "diagnostic", "market", "competitor",
                "research", "decision", "forecasting", "knowledge", "quality",
            )]
            if suggested and "quality" not in suggested:
                suggested.append("quality")
            # Keep planner output as base; enrich sequential list if LLM adds useful agents
            for a in suggested:
                if a not in task.plan.agents_required:
                    task.plan.agents_required.append(a)
                    if a not in task.plan.sequential_steps:
                        task.plan.sequential_steps.insert(-1 if "quality" in task.plan.sequential_steps else len(task.plan.sequential_steps), a)

        task = await self.orchestrator.run(task.task_id)

        # Natural language synthesis
        synthesis_source = {
            "state": task.state.value if hasattr(task.state, "value") else str(task.state),
            "objective": task.objective,
            "results": task.results,
            "errors": task.errors,
            "evidence_ids": task.evidence_ids,
            "plan_hint": plan_hint,
        }
        if self.llm.available(api_key):
            reply_text = self.llm.synthesise_reply(req.message, synthesis_source, history[:-1], api_key=api_key)
        else:
            reply_text = self._deterministic_reply(req.message, task)

        assistant_msg = ChatMessage(
            role="assistant",
            content=reply_text,
            task_id=task.task_id,
            meta={
                "objective": task.objective,
                "state": task.state.value if hasattr(task.state, "value") else str(task.state),
                "agents": task.agents_assigned,
                "llm_provider": self.llm.provider(api_key),
                "qa": (task.results.get("quality") or {}).get("qa_result"),
            },
        )
        session.messages.append(assistant_msg)
        session.updated_at = datetime.now(timezone.utc).isoformat() + "Z"
        if session.title == "New chat" and req.message:
            session.title = req.message[:48] + ("…" if len(req.message) > 48 else "")


        # Workforce mission path for multi-step objectives (non-breaking)
        try:
            from orchestrator.workforce import workforce
            from schemas.missions import MissionCreate, MissionPriority
            if len(req.message.split()) >= 6:
                mission = await workforce.create_and_run(
                    MissionCreate(
                        objective=req.message,
                        organisation_id=organisation_id,
                        user_id=user_id,
                        context=context,
                        priority=MissionPriority.NORMAL,
                    ),
                    api_key=api_key,
                    auto_run=True,
                )
                if mission.result and mission.result.summary:
                    # Prefer mission synthesis when available
                    reply_text = mission.result.summary
                    if mission.result.findings:
                        reply_text += "\n\n**Findings**\n"
                        for f in mission.result.findings[:8]:
                            if isinstance(f, dict):
                                reply_text += f"- {f.get('summary') or f.get('objective') or f}\n"
                    if mission.result.actions:
                        reply_text += "\n\n**Actions**\n" + "\n".join(f"- {a}" for a in mission.result.actions[:8])
                    if mission.result.limitations:
                        reply_text += "\n\n**Limitations**\n" + "\n".join(f"- {x}" for x in mission.result.limitations[:5])
                    assistant_msg.meta["mission_id"] = mission.mission_id
                    assistant_msg.meta["mission_status"] = mission.status.value
                    assistant_msg.content = reply_text
        except Exception as _mission_err:
            # Fall back to classic task synthesis already computed
            pass

        return {
            "session_id": session.session_id,
            "title": session.title,
            "message": assistant_msg.model_dump(),
            "task_id": task.task_id,
            "task_state": task.state.value if hasattr(task.state, "value") else str(task.state),
            "llm_provider": self.llm.provider(api_key),
            "messages": [m.model_dump() for m in session.messages],
        }

    def _deterministic_reply(self, user_message: str, task) -> str:
        lines = [
            f"**Objective:** {task.objective or 'general analysis'}",
            f"**Status:** {task.state.value if hasattr(task.state, 'value') else task.state}",
            "",
        ]
        synth = task.results.get("synthesis") or {}
        if synth.get("executive_summary"):
            lines.append("**Summary**")
            lines.append(str(synth["executive_summary"]))
            lines.append("")
        for agent_id, result in (task.results or {}).items():
            if agent_id in ("synthesis", "quality"):
                continue
            if not isinstance(result, dict):
                continue
            summary = result.get("summary")
            if summary:
                lines.append(f"**{agent_id.replace('_', ' ').title()}**")
                lines.append(str(summary))
                lines.append("")
        qa = task.results.get("quality") or {}
        if qa.get("qa_result"):
            lines.append(f"**Quality assurance:** {qa['qa_result']}")
        if not self.llm.available(None):
            lines.append("")
            lines.append(
                "_Add your API key in Settings for fuller natural-language synthesis._"
            )
        return "\n".join(lines).strip()
