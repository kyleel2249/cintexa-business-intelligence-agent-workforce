"""Correlation context propagation."""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional

from schemas.common import new_id


@dataclass
class TelemetryContext:
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    organisation_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    workflow_id: Optional[str] = None
    task_id: Optional[str] = None
    agent_id: Optional[str] = None
    agent_key: Optional[str] = None
    agent_version: Optional[str] = None
    tool_execution_id: Optional[str] = None
    evaluation_id: Optional[str] = None
    recovery_id: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None

    def ensure_ids(self) -> "TelemetryContext":
        if not self.trace_id:
            self.trace_id = new_id("TR-")
        if not self.correlation_id:
            self.correlation_id = self.request_id or new_id("COR-")
        if not self.request_id:
            self.request_id = self.correlation_id
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    def child_span(self, span_id: Optional[str] = None) -> "TelemetryContext":
        c = TelemetryContext(**asdict(self))
        c.parent_span_id = self.span_id
        c.span_id = span_id or new_id("SP-")
        return c


_ctx: contextvars.ContextVar[Optional[TelemetryContext]] = contextvars.ContextVar("tel_ctx", default=None)


def get_context() -> Optional[TelemetryContext]:
    return _ctx.get()


def set_context(ctx: Optional[TelemetryContext]) -> None:
    _ctx.set(ctx)


@contextmanager
def with_span(operation: str, component: str = "app", **attrs):
    from observability.tracing import tracer

    parent = get_context() or TelemetryContext().ensure_ids()
    parent.ensure_ids()
    child = parent.child_span()
    token = _ctx.set(child)
    span = tracer.start_span(
        operation=operation,
        component=component,
        ctx=child,
        attributes=attrs,
    )
    try:
        yield span
        tracer.end_span(span, status="OK")
    except Exception as e:
        tracer.end_span(span, status="ERROR", error=str(e)[:500])
        raise
    finally:
        _ctx.reset(token)
