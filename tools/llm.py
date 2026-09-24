"""LLM adapter — OpenAI primary, Anthropic fallback. Used by orchestrator and agents."""

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


class LLMClient:
    """Thin multi-provider client. Returns plain text or parsed JSON when asked."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._openai = None
        self._anthropic = None

    @property
    def available(self) -> bool:
        return bool(self.settings.openai_api_key or self.settings.anthropic_api_key)

    @property
    def provider(self) -> str:
        if self.settings.openai_api_key:
            return "openai"
        if self.settings.anthropic_api_key:
            return "anthropic"
        return "none"

    def _get_openai(self):
        if self._openai is None and self.settings.openai_api_key:
            from openai import OpenAI
            self._openai = OpenAI(api_key=self.settings.openai_api_key)
        return self._openai

    def _get_anthropic(self):
        if self._anthropic is None and self.settings.anthropic_api_key:
            from anthropic import Anthropic
            self._anthropic = Anthropic(api_key=self.settings.anthropic_api_key)
        return self._anthropic

    def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        system: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        json_mode: bool = False,
    ) -> str:
        """
        messages: list of {role: user|assistant, content: str}
        """
        sys = (system or SYSTEM_GUARDRAILS).strip()
        if not self.available:
            return self._offline_reply(messages)

        if self.provider == "openai":
            return self._openai_chat(messages, sys, temperature, max_tokens, json_mode)
        return self._anthropic_chat(messages, sys, temperature, max_tokens)

    def _openai_chat(
        self,
        messages: List[Dict[str, str]],
        system: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> str:
        client = self._get_openai()
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
    ) -> str:
        client = self._get_anthropic()
        # Anthropic wants alternating user/assistant; system is separate
        resp = client.messages.create(
            model=self.settings.anthropic_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": m["role"], "content": m["content"]} for m in messages if m["role"] in ("user", "assistant")],
        )
        parts = []
        for block in resp.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts).strip()

    def _offline_reply(self, messages: List[Dict[str, str]]) -> str:
        last = messages[-1]["content"] if messages else ""
        return (
            "No LLM API key is configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY in the environment "
            "for full natural-language planning and synthesis.\n\n"
            "Your message was still accepted by the orchestrator. Specialist agents can run deterministic "
            f"paths (diagnostics, forecasts from your data) without an LLM.\n\nLast user message preview: {last[:280]}"
        )

    def plan_objective(self, user_message: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """Use LLM to refine objective and agent selection when available."""
        prompt = (
            "Given this business request, return JSON with keys: "
            "objective (short snake_case), agents (array of agent ids from: "
            "strategy, intelligence, diagnostic, market, competitor, research, decision, forecasting, knowledge, quality), "
            "needs_web_research (bool), needs_user_data (bool), summary (one sentence).\n"
            f"Request: {user_message}"
        )
        messages = list(history or [])
        messages.append({"role": "user", "content": prompt})
        if not self.available:
            return {}
        try:
            raw = self.chat(messages, temperature=0.1, max_tokens=600, json_mode=self.provider == "openai")
            # Extract JSON if wrapped in markdown
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
    ) -> str:
        """Turn structured agent outputs into a clear executive chat reply."""
        compact = json.dumps(task_results, default=str)[:12000]
        prompt = (
            "You are the CINTEXA BI assistant speaking to the user in a chat.\n"
            "Using only the structured agent results below, write a clear, helpful reply in British English.\n"
            "Structure with short sections where useful (Summary, Findings, Risks, Recommendations).\n"
            "Do not invent numbers or sources not present in the results.\n"
            "If data was unavailable, say so plainly.\n\n"
            f"User request:\n{user_message}\n\n"
            f"Agent results (JSON):\n{compact}"
        )
        messages = list(history or [])[-6:]
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, temperature=0.35, max_tokens=2500)


_client: Optional[LLMClient] = None


def get_llm() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
