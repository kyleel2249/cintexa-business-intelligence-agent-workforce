"""LLM adapter — OpenAI primary, Anthropic fallback.

Server env keys (OPENAI_API_KEY / ANTHROPIC_API_KEY) are optional defaults.
Per-request user keys may be passed via api_key= and are never logged or stored.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from config.settings import get_settings

SYSTEM_GUARDRAILS = """You are part of CINTEXA Business Intelligence, a multi-agent workforce.
Rules you must follow:
- Never invent market statistics, competitor figures, financial numbers, citations, or company facts.
- If data is missing, say it is unavailable.
- Prefer structured, evidence-aware answers.
- Distinguish measured, estimated, inferred, and user-provided information.
- You inform decisions; you do not make irreversible decisions for the user.
- Be concise, professional, and specific to the business request.
"""


def _detect_provider(api_key: str) -> str:
    """Heuristic: Anthropic keys often start with sk-ant-; otherwise treat as OpenAI."""
    k = (api_key or "").strip()
    if k.startswith("sk-ant-"):
        return "anthropic"
    if k:
        return "openai"
    return "none"


class LLMClient:
    """Multi-provider client. Prefer per-request api_key; fall back to server env."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def resolve_key(self, api_key: Optional[str] = None) -> str:
        key = (api_key or "").strip()
        if key:
            return key
        return (self.settings.openai_api_key or self.settings.anthropic_api_key or "").strip()

    def available(self, api_key: Optional[str] = None) -> bool:
        return bool(self.resolve_key(api_key))

    def provider(self, api_key: Optional[str] = None) -> str:
        key = self.resolve_key(api_key)
        if not key:
            return "none"
        # Explicit env preference when no per-request key
        if not (api_key or "").strip():
            if self.settings.openai_api_key:
                return "openai"
            if self.settings.anthropic_api_key:
                return "anthropic"
        return _detect_provider(key)

    def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        system: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        json_mode: bool = False,
        api_key: Optional[str] = None,
    ) -> str:
        sys = (system or SYSTEM_GUARDRAILS).strip()
        key = self.resolve_key(api_key)
        if not key:
            return self._offline_reply(messages)

        prov = self.provider(api_key)
        if prov == "openai":
            return self._openai_chat(messages, sys, temperature, max_tokens, json_mode, key)
        if prov == "anthropic":
            return self._anthropic_chat(messages, sys, temperature, max_tokens, key)
        return self._offline_reply(messages)

    def _openai_chat(
        self,
        messages: List[Dict[str, str]],
        system: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
        api_key: str,
    ) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        payload: List[Dict[str, str]] = [{"role": "system", "content": system}]
        payload.extend(messages)
        kwargs: Dict[str, Any] = {
            "model": self.settings.openai_model,
            "messages": payload,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        return (resp.choices[0].message.content or "").strip()

    def _anthropic_chat(
        self,
        messages: List[Dict[str, str]],
        system: str,
        temperature: float,
        max_tokens: int,
        api_key: str,
    ) -> str:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=self.settings.anthropic_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[
                {"role": m["role"], "content": m["content"]}
                for m in messages
                if m["role"] in ("user", "assistant")
            ],
        )
        parts = []
        for block in resp.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts).strip()

    def _offline_reply(self, messages: List[Dict[str, str]]) -> str:
        last = messages[-1]["content"] if messages else ""
        return (
            "No API key is configured. Open Settings and enter your OpenAI API key "
            "(or Anthropic key starting with sk-ant-). "
            "Specialist agents can still run deterministic paths without an LLM.\n\n"
            f"Last message preview: {last[:280]}"
        )

    def plan_objective(
        self,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        prompt = (
            "Given this business request, return JSON with keys: "
            "objective (short snake_case), agents (array of agent ids from: "
            "strategy, intelligence, diagnostic, market, competitor, research, decision, "
            "forecasting, knowledge, quality), "
            "needs_web_research (bool), needs_user_data (bool), summary (one sentence).\n"
            f"Request: {user_message}"
        )
        messages = list(history or [])
        messages.append({"role": "user", "content": prompt})
        if not self.available(api_key):
            return {}
        try:
            raw = self.chat(
                messages,
                temperature=0.1,
                max_tokens=600,
                json_mode=self.provider(api_key) == "openai",
                api_key=api_key,
            )
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                return json.loads(raw[start : end + 1])
        except Exception:
            return {}
        return {}

    def synthesise_reply(
        self,
        user_message: str,
        task_results: Dict[str, Any],
        history: Optional[List[Dict[str, str]]] = None,
        api_key: Optional[str] = None,
    ) -> str:
        compact = json.dumps(task_results, default=str)[:12000]
        prompt = (
            "You are the CINTEXA BI assistant speaking to the user in a chat.\n"
            "Using only the structured agent results below, write a clear, helpful reply "
            "in British English.\n"
            "Structure with short sections where useful (Summary, Findings, Risks, Recommendations).\n"
            "Do not invent numbers or sources not present in the results.\n"
            "If data was unavailable, say so plainly.\n\n"
            f"User request:\n{user_message}\n\n"
            f"Agent results (JSON):\n{compact}"
        )
        messages = list(history or [])[-6:]
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, temperature=0.35, max_tokens=2500, api_key=api_key)


_client: Optional[LLMClient] = None


def get_llm() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
