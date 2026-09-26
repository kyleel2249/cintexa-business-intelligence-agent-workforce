"""Telemetry persistence — org-scoped, non-authoritative derived store."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from observability.models_db import ObsLog, ObsSpan
from observability.logging import redact_secrets


class TelemetryStore:
    def append_log(self, record: Dict[str, Any]) -> str:
        lid = new_id("LOG-")
        safe = redact_secrets(record)
        with UnitOfWork() as uow:
            uow.session.add(
                ObsLog(
                    log_id=lid,
                    organisation_id=safe.get("organisation_id"),
                    correlation_id=safe.get("correlation_id"),
                    trace_id=safe.get("trace_id"),
                    severity=safe.get("severity") or "INFO",
                    component=safe.get("component") or "app",
                    message=str(safe.get("message") or "")[:4000],
                    payload=safe,
                )
            )
        return lid

    def save_span(self, span) -> None:
        d = span.to_dict() if hasattr(span, "to_dict") else span
        with UnitOfWork() as uow:
            existing = uow.session.get(ObsSpan, d["span_id"])
            if existing:
                existing.end_time = d.get("end_time")
                existing.duration_ms = d.get("duration_ms")
                existing.status = d.get("status")
                existing.error = d.get("error")
                existing.attributes = d.get("attributes") or {}
            else:
                uow.session.add(
                    ObsSpan(
                        span_id=d["span_id"],
                        trace_id=d["trace_id"],
                        parent_span_id=d.get("parent_span_id"),
                        organisation_id=d.get("organisation_id"),
                        correlation_id=d.get("correlation_id"),
                        workflow_id=d.get("workflow_id"),
                        task_id=d.get("task_id"),
                        agent_id=d.get("agent_id"),
                        operation=d["operation"],
                        component=d.get("component") or "app",
                        start_time=d["start_time"],
                        end_time=d.get("end_time"),
                        duration_ms=d.get("duration_ms"),
                        status=d.get("status") or "RUNNING",
                        attributes=d.get("attributes") or {},
                        error=d.get("error"),
                    )
                )

    def load_trace(self, trace_id: str, organisation_id: Optional[str] = None) -> List[dict]:
        with UnitOfWork() as uow:
            q = uow.session.query(ObsSpan).filter_by(trace_id=trace_id)
            if organisation_id:
                q = q.filter(
                    (ObsSpan.organisation_id == organisation_id) | (ObsSpan.organisation_id.is_(None))
                )
            rows = q.order_by(ObsSpan.start_time.asc()).all()
            return [
                {
                    "span_id": r.span_id,
                    "trace_id": r.trace_id,
                    "parent_span_id": r.parent_span_id,
                    "operation": r.operation,
                    "component": r.component,
                    "start_time": r.start_time,
                    "end_time": r.end_time,
                    "duration_ms": r.duration_ms,
                    "status": r.status,
                    "attributes": r.attributes or {},
                    "error": r.error,
                    "organisation_id": r.organisation_id,
                    "correlation_id": r.correlation_id,
                    "workflow_id": r.workflow_id,
                    "task_id": r.task_id,
                    "agent_id": r.agent_id,
                }
                for r in rows
            ]

    def query_logs(
        self, organisation_id: str, *, limit: int = 100, correlation_id: Optional[str] = None
    ) -> List[dict]:
        with UnitOfWork() as uow:
            q = uow.session.query(ObsLog).filter_by(organisation_id=organisation_id)
            if correlation_id:
                q = q.filter_by(correlation_id=correlation_id)
            rows = q.order_by(ObsLog.created_at.desc()).limit(limit).all()
            return [
                {
                    "log_id": r.log_id,
                    "severity": r.severity,
                    "component": r.component,
                    "message": r.message,
                    "correlation_id": r.correlation_id,
                    "trace_id": r.trace_id,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
