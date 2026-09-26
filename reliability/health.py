"""Dependency health model."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

from events.bus import bus


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


@dataclass
class DependencyHealth:
    name: str
    status: HealthStatus = HealthStatus.UNKNOWN
    last_success_at: float = 0.0
    last_failure_at: float = 0.0
    consecutive_failures: int = 0
    success_count: int = 0
    failure_count: int = 0
    latency_ms_ema: float = 0.0
    circuit_state: str = "CLOSED"
    details: dict = field(default_factory=dict)

    def record_success(self, latency_ms: float = 0.0) -> None:
        self.last_success_at = time.time()
        self.consecutive_failures = 0
        self.success_count += 1
        if self.latency_ms_ema <= 0:
            self.latency_ms_ema = latency_ms
        else:
            self.latency_ms_ema = 0.8 * self.latency_ms_ema + 0.2 * latency_ms
        prev = self.status
        self.status = HealthStatus.HEALTHY
        if prev != HealthStatus.HEALTHY:
            bus.publish("dependency.recovered", {"name": self.name})

    def record_failure(self) -> None:
        self.last_failure_at = time.time()
        self.consecutive_failures += 1
        self.failure_count += 1
        prev = self.status
        if self.consecutive_failures >= 5:
            self.status = HealthStatus.UNAVAILABLE
        elif self.consecutive_failures >= 2:
            self.status = HealthStatus.DEGRADED
        if prev != self.status and self.status in (HealthStatus.DEGRADED, HealthStatus.UNAVAILABLE):
            bus.publish("dependency.degraded", {"name": self.name, "status": self.status.value})

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "consecutive_failures": self.consecutive_failures,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "latency_ms_ema": self.latency_ms_ema,
            "circuit_state": self.circuit_state,
        }


class HealthRegistry:
    def __init__(self):
        self._deps: Dict[str, DependencyHealth] = {}

    def get(self, name: str) -> DependencyHealth:
        if name not in self._deps:
            self._deps[name] = DependencyHealth(name=name)
        return self._deps[name]

    def is_routable(self, name: str) -> bool:
        h = self.get(name)
        return h.status != HealthStatus.UNAVAILABLE

    def all(self) -> list:
        return [d.to_dict() for d in self._deps.values()]


health_registry = HealthRegistry()
