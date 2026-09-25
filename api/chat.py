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
from tools.web import extract_urls, browse_urls, format_browse_context


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

        # Browse any URLs in the message (and optional context urls)
        url_list = extract_urls(req.message)
        extra = (req.context or {}).get("urls") if isinstance(req.context, dict) else None
        if isinstance(extra, list):
            url_list.extend([u for u in extra if isinstance(u, str)])
        pages = await browse_urls(url_list) if url_list else []
        browse_ctx = format_browse_context(pages) if pages else ""

        # Natural language synthesis with web evidence + memory loop
        synthesis_source = {
            "state": task.state.value if hasattr(task.state, "value") else str(task.state),
            "objective": task.objective,
            "results": task.results,
            "errors": task.errors,
            "evidence_ids": task.evidence_ids,
            "plan_hint": plan_hint,
            "web_sources": [
                {"url": p.get("url"), "ok": p.get("ok"), "title": p.get("title")} for p in pages
            ],
        }
        if self.llm.available(api_key):
            hist = history[:-1] if history else []
            prompt_extra = ""
            if browse_ctx:
                prompt_extra = (
                    "\n\nBrowsed page evidence (use as primary sources; do not invent):\n"
                    + browse_ctx[:20000]
                )
            reply_text = self.llm.synthesise_reply(
                req.message + prompt_extra, synthesis_source, hist, api_key=api_key
            )
            # Completion loop: if model asks for more URLs, fetch and resynthesise (max 3)
            import re as _re
            for _ in range(3):
                m = _re.search(r"NEED_URLS:\s*(.+)", reply_text)
                if not m:
                    break
                more_urls = extract_urls(m.group(1).replace("|", " "))
                if not more_urls:
                    break
                more_pages = await browse_urls(more_urls)
                pages.extend(more_pages)
                browse_ctx = format_browse_context(pages)
                synthesis_source["web_sources"] = [
                    {"url": p.get("url"), "ok": p.get("ok"), "title": p.get("title")} for p in pages
                ]
                reply_text = self.llm.synthesise_reply(
                    req.message
                    + "\n\nAdditional browsed evidence:\n"
                    + browse_ctx[:20000]
                    + "\n\nContinue and finish the request. Do not emit NEED_URLS unless essential.",
                    synthesis_source,
                    hist,
                    api_key=api_key,
                )
            reply_text = _re.sub(r"^NEED_URLS:.*$", "", reply_text, flags=_re.M).strip()
        else:
            reply_text = self._deterministic_reply(req.message, task)
            if pages:
                reply_text += "\n\n**Sources fetched:** " + ", ".join(
                    p.get("url", "") for p in pages if p.get("ok")
                )

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
                "sources": [
                    {"url": p.get("url"), "ok": p.get("ok"), "title": p.get("title")} for p in pages
                ],
            },
        )
        session.messages.append(assistant_msg)
        session.updated_at = datetime.now(timezone.utc).isoformat() + "Z"
        if session.title == "New chat" and req.message:
            session.title = req.message[:48] + ("…" if len(req.message) > 48 else "")

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
