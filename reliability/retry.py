"""Retry engine with exponential backoff, jitter, and budgets."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from events.bus import bus
from reliability.taxonomy import FailureCategory, FailureDecision, classify_failure


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    min_delay_sec: float = 0.05
    max_delay_sec: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True
    total_deadline_sec: Optional[float] = None
    retryable_categories: Optional[set] = None


@dataclass
class RetryAttempt:
    attempt: int
    started_at: float
    ended_at: float = 0.0
    success: bool = False
    error: str = ""
    category: str = ""
    delay_before_sec: float = 0.0


@dataclass
class RetryResult:
    success: bool
    result: Any = None
    attempts: list = field(default_factory=list)
    decision: Optional[FailureDecision] = None
    exhausted: bool = False


class RetryBudget:
    """Prevents retry storms per scope key."""

    def __init__(self, max_retries_per_window: int = 50, window_sec: float = 60.0):
        self.max = max_retries_per_window
        self.window = window_sec
        self._counts: Dict[str, list] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        arr = self._counts.setdefault(key, [])
        self._counts[key] = [t for t in arr if now - t < self.window]
        if len(self._counts[key]) >= self.max:
            return False
        self._counts[key].append(now)
        return True


_global_budget = RetryBudget()


class RetryEngine:
    def __init__(self, policy: Optional[RetryPolicy] = None, budget: Optional[RetryBudget] = None):
        self.policy = policy or RetryPolicy()
        self.budget = budget or _global_budget

    def delay_for(self, attempt: int) -> float:
        p = self.policy
        delay = min(p.max_delay_sec, p.min_delay_sec * (p.exponential_base ** (attempt - 1)))
        if p.jitter:
            delay = delay * (0.5 + random.random())
        return max(p.min_delay_sec, delay)

    def run(
        self,
        fn: Callable[[], Any],
        *,
        organisation_id: str = "",
        scope_key: str = "default",
        correlation_id: Optional[str] = None,
        sleep: bool = True,
    ) -> RetryResult:
        p = self.policy
        attempts: list = []
        t0 = time.time()
        last_decision: Optional[FailureDecision] = None

        for attempt in range(1, p.max_attempts + 1):
            if p.total_deadline_sec is not None and (time.time() - t0) >= p.total_deadline_sec:
                break
            if attempt > 1 and not self.budget.allow(f"{organisation_id}:{scope_key}"):
                last_decision = FailureDecision(
                    category=FailureCategory.RESOURCE_EXHAUSTION,
                    retryable=False,
                    terminal=True,
                    reason="Retry budget exhausted",
                )
                break

            delay = self.delay_for(attempt) if attempt > 1 else 0.0
            if delay and sleep:
                # respect remaining deadline
                if p.total_deadline_sec is not None:
                    remaining = p.total_deadline_sec - (time.time() - t0)
                    delay = min(delay, max(0.0, remaining))
                time.sleep(delay)

            started = time.time()
            try:
                result = fn()
                rec = RetryAttempt(attempt=attempt, started_at=started, ended_at=time.time(), success=True, delay_before_sec=delay)
                attempts.append(rec)
                bus.publish(
                    "retry.succeeded",
                    {"attempt": attempt, "scope": scope_key, "correlation_id": correlation_id},
                    organisation_id=organisation_id or None,
                )
                return RetryResult(success=True, result=result, attempts=attempts)
            except Exception as e:
                decision = classify_failure(e, attempt=attempt, max_retries=p.max_attempts)
                last_decision = decision
                rec = RetryAttempt(
                    attempt=attempt,
                    started_at=started,
                    ended_at=time.time(),
                    success=False,
                    error=str(e)[:500],
                    category=decision.category.value,
                    delay_before_sec=delay,
                )
                attempts.append(rec)
                bus.publish(
                    "retry.scheduled" if decision.retryable else "retry.exhausted",
                    {
                        "attempt": attempt,
                        "category": decision.category.value,
                        "retryable": decision.retryable,
                        "scope": scope_key,
                        "correlation_id": correlation_id,
                    },
                    organisation_id=organisation_id or None,
                )
                if not decision.retryable:
                    return RetryResult(success=False, attempts=attempts, decision=decision, exhausted=True)

        return RetryResult(success=False, attempts=attempts, decision=last_decision, exhausted=True)
