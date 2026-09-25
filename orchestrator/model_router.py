"""Model routing and fallback across OpenRouter / OpenAI / Anthropic / deterministic."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from orchestrator.policies import DEFAULT_POLICIES


@dataclass
class ModelChoice:
    provider: str
    model: str
    reason: str
    fallback_chain: List[str] = field(default_factory=list)


class ModelRouter:
    def __init__(self) -> None:
        self.policies = DEFAULT_POLICIES
        self._history: List[Dict[str, Any]] = []

    def select(
        self,
        *,
        task_complexity: str = "medium",
        needs_reasoning: bool = True,
        latency_sensitive: bool = False,
        api_key: Optional[str] = None,
    ) -> ModelChoice:
        key = (api_key or "").strip()
        chain = list(self.policies.model_fallback_chain)
        if key.startswith("sk-or-"):
            primary = "openrouter"
            model = "openai/gpt-4o"
        elif key.startswith("sk-ant-"):
            primary = "anthropic"
            model = "claude-3-5-sonnet-20241022"
        elif key:
            primary = "openai"
            model = "gpt-4o"
        else:
            primary = "deterministic"
            model = "none"
        if latency_sensitive and primary == "openrouter":
            model = "openai/gpt-4o-mini"
        if task_complexity == "low":
            if primary == "openrouter":
                model = "openai/gpt-4o-mini"
            elif primary == "openai":
                model = "gpt-4o-mini"
        choice = ModelChoice(
            provider=primary,
            model=model,
            reason=f"complexity={task_complexity} reasoning={needs_reasoning} latency={latency_sensitive}",
            fallback_chain=[p for p in chain if p != primary] + ["deterministic"],
        )
        self._history.append({"provider": primary, "model": model, "reason": choice.reason})
        return choice

    def record_fallback(self, from_provider: str, to_provider: str, reason: str) -> None:
        self._history.append(
            {"fallback_from": from_provider, "fallback_to": to_provider, "reason": reason}
        )


model_router = ModelRouter()
