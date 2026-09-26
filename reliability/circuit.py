"""Per-dependency circuit breaker."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

from events.bus import bus


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 5
    success_threshold: int = 2
    cooldown_sec: float = 30.0
    window_sec: float = 60.0

    state: CircuitState = CircuitState.CLOSED
    failures: list = field(default_factory=list)
    consecutive_successes: int = 0
    opened_at: float = 0.0
    half_open_trials: int = 0
    max_half_open: int = 1

    def _prune(self) -> None:
        now = time.time()
        self.failures = [t for t in self.failures if now - t < self.window_sec]

    def allow(self) -> bool:
        now = time.time()
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if now - self.opened_at >= self.cooldown_sec:
                self.state = CircuitState.HALF_OPEN
                self.half_open_trials = 0
                self.consecutive_successes = 0
                bus.publish("circuit.half_opened", {"name": self.name})
                return True
            return False
        # HALF_OPEN
        if self.half_open_trials >= self.max_half_open:
            return False
        self.half_open_trials += 1
        return True

    def record_success(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self.consecutive_successes += 1
            if self.consecutive_successes >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.failures.clear()
                self.consecutive_successes = 0
                bus.publish("circuit.closed", {"name": self.name})
        elif self.state == CircuitState.CLOSED:
            self.failures.clear()

    def record_failure(self) -> None:
        now = time.time()
        self._prune()
        self.failures.append(now)
        self.consecutive_successes = 0
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.opened_at = now
            bus.publish("circuit.opened", {"name": self.name, "reason": "half_open_failure"})
            return
        if len(self.failures) >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.opened_at = now
            bus.publish("circuit.opened", {"name": self.name, "reason": "threshold"})

    def status(self) -> dict:
        self._prune()
        return {
            "name": self.name,
            "state": self.state.value,
            "failures_in_window": len(self.failures),
            "opened_at": self.opened_at or None,
        }


class CircuitRegistry:
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}

    def get(self, name: str, **kwargs) -> CircuitBreaker:
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name=name, **kwargs)
        return self._breakers[name]

    def all_status(self) -> list:
        return [b.status() for b in self._breakers.values()]


# process-local registry; durable mirror optional via models
circuits = CircuitRegistry()
