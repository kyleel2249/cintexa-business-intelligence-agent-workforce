"""In-process metrics with controlled cardinality + durable snapshots."""

from __future__ import annotations

import statistics
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class Histogram:
    values: List[float] = field(default_factory=list)

    def observe(self, v: float) -> None:
        self.values.append(float(v))
        if len(self.values) > 5000:
            self.values = self.values[-2500:]

    def snapshot(self) -> dict:
        if not self.values:
            return {"count": 0}
        vs = sorted(self.values)
        n = len(vs)

        def pct(p: float) -> float:
            idx = min(n - 1, max(0, int(p * (n - 1))))
            return vs[idx]

        return {
            "count": n,
            "sum": sum(vs),
            "min": vs[0],
            "max": vs[-1],
            "mean": statistics.fmean(vs),
            "p50": pct(0.50),
            "p95": pct(0.95),
            "p99": pct(0.99),
        }


class MetricsRegistry:
    def __init__(self):
        self._counters: Dict[Tuple[str, str], int] = defaultdict(int)
        self._histograms: Dict[Tuple[str, str], Histogram] = {}

    def _key(self, name: str, organisation_id: str = "") -> Tuple[str, str]:
        # controlled cardinality: only name + org (not request_id)
        return (name, organisation_id or "_")

    def incr(self, name: str, organisation_id: str = "", by: int = 1) -> None:
        self._counters[self._key(name, organisation_id)] += by

    def observe(self, name: str, value: float, organisation_id: str = "") -> None:
        k = self._key(name, organisation_id)
        if k not in self._histograms:
            self._histograms[k] = Histogram()
        self._histograms[k].observe(value)

    def snapshot(self, organisation_id: Optional[str] = None) -> dict:
        counters = {}
        for (name, org), val in self._counters.items():
            if organisation_id and org not in (organisation_id, "_"):
                continue
            counters[f"{name}|{org}"] = val
        hist = {}
        for (name, org), h in self._histograms.items():
            if organisation_id and org not in (organisation_id, "_"):
                continue
            hist[f"{name}|{org}"] = h.snapshot()
        return {"counters": counters, "histograms": hist, "captured_at": time.time()}


metrics = MetricsRegistry()
