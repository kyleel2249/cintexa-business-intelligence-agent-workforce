"""Distributed tracing spans + timelines."""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from schemas.common import new_id
from observability.context import TelemetryContext
from observability.logging import redact_secrets


@dataclass
class Span:
    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    operation: str
    component: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: str = "RUNNING"
    attributes: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    organisation_id: Optional[str] = None
    correlation_id: Optional[str] = None
    workflow_id: Optional[str] = None
    task_id: Optional[str] = None
    agent_id: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["attributes"] = redact_secrets(d.get("attributes") or {})
        d["error"] = redact_secrets(d["error"]) if d.get("error") else None
        return d


class Tracer:
    def __init__(self):
        self._spans: Dict[str, List[Span]] = {}  # trace_id -> spans (cache)
        self._active: Dict[str, Span] = {}

    def start_span(
        self,
        *,
        operation: str,
        component: str,
        ctx: TelemetryContext,
        attributes: Optional[Dict] = None,
    ) -> Span:
        ctx.ensure_ids()
        span = Span(
            span_id=ctx.span_id or new_id("SP-"),
            trace_id=ctx.trace_id or new_id("TR-"),
            parent_span_id=ctx.parent_span_id,
            operation=operation,
            component=component,
            start_time=time.time(),
            attributes=redact_secrets(attributes or {}),
            organisation_id=ctx.organisation_id,
            correlation_id=ctx.correlation_id,
            workflow_id=ctx.workflow_id,
            task_id=ctx.task_id,
            agent_id=ctx.agent_id,
        )
        self._active[span.span_id] = span
        self._spans.setdefault(span.trace_id, []).append(span)
        return span

    def end_span(self, span: Span, status: str = "OK", error: Optional[str] = None) -> Span:
        span.end_time = time.time()
        span.duration_ms = (span.end_time - span.start_time) * 1000.0
        span.status = status
        if error:
            span.error = redact_secrets(error) if isinstance(error, str) else str(error)
        self._active.pop(span.span_id, None)
        try:
            from observability.store import TelemetryStore
            TelemetryStore().save_span(span)
        except Exception:
            pass
        try:
            from observability.otlp_export import export_span
            export_span(span.to_dict())
        except Exception:
            pass
        from observability.metrics import metrics
        metrics.observe(f"span.{span.component}.latency_ms", span.duration_ms or 0, span.organisation_id or "")
        metrics.incr(f"span.{span.component}.{status.lower()}", span.organisation_id or "")
        return span

    def get_trace(self, trace_id: str, organisation_id: Optional[str] = None) -> List[dict]:
        spans = self._spans.get(trace_id) or []
        out = [s.to_dict() for s in spans]
        if organisation_id:
            out = [s for s in out if s.get("organisation_id") in (None, organisation_id)]
        # also load from store
        try:
            from observability.store import TelemetryStore
            stored = TelemetryStore().load_trace(trace_id, organisation_id)
            ids = {s["span_id"] for s in out}
            for s in stored:
                if s["span_id"] not in ids:
                    out.append(s)
        except Exception:
            pass
        return sorted(out, key=lambda x: x.get("start_time") or 0)

    def timeline(self, trace_id: str, organisation_id: Optional[str] = None) -> dict:
        spans = self.get_trace(trace_id, organisation_id)
        return {
            "trace_id": trace_id,
            "spans": spans,
            "span_count": len(spans),
            "total_duration_ms": max((s.get("duration_ms") or 0) for s in spans) if spans else 0,
        }


tracer = Tracer()
