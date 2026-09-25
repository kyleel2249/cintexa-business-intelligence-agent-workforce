"""Intelligent failure recovery — classify, retry, switch agent/tool, replan."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from schemas.missions import FailureClass, MissionTask


class RecoveryManager:
    def classify(self, exc: Exception) -> FailureClass:
        msg = str(exc).lower()
        if "timeout" in msg:
            return FailureClass.TIMEOUT
        if "permission" in msg or "forbidden" in msg or "unauthorized" in msg:
            return FailureClass.PERMISSION_FAILURE
        if "validat" in msg or "schema" in msg:
            return FailureClass.VALIDATION_FAILURE
        if "tool" in msg:
            return FailureClass.TOOL_FAILURE
        if any(x in msg for x in ("model", "llm", "openai", "anthropic", "openrouter")):
            return FailureClass.MODEL_FAILURE
        if "data" in msg or "missing" in msg:
            return FailureClass.DATA_FAILURE
        if "depend" in msg:
            return FailureClass.DEPENDENCY_FAILURE
        if "resource" in msg or "memory" in msg:
            return FailureClass.RESOURCE_FAILURE
        if "logic" in msg or "assert" in msg:
            return FailureClass.LOGIC_FAILURE
        return FailureClass.UNKNOWN_FAILURE

    def should_retry(self, klass: FailureClass, attempts: int, max_attempts: int) -> bool:
        if attempts >= max_attempts:
            return False
        return klass in {
            FailureClass.TIMEOUT,
            FailureClass.TOOL_FAILURE,
            FailureClass.MODEL_FAILURE,
            FailureClass.RESOURCE_FAILURE,
            FailureClass.UNKNOWN_FAILURE,
        }

    def next_agent(self, failed_agent: str, alternatives: list) -> Optional[str]:
        for a in alternatives:
            if a and a != failed_agent:
                return a
        return None

    def plan_recovery(self, task: MissionTask, exc: Exception) -> Dict[str, Any]:
        klass = self.classify(exc)
        return {
            "failure_class": klass.value,
            "retry": self.should_retry(klass, task.attempts, task.max_attempts or 2),
            "escalate": klass
            in {FailureClass.PERMISSION_FAILURE, FailureClass.LOGIC_FAILURE},
            "replan_hint": klass
            in {FailureClass.DATA_FAILURE, FailureClass.DEPENDENCY_FAILURE},
        }


recovery_manager = RecoveryManager()
