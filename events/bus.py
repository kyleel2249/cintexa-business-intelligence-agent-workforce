"""Event bus — durable storage is authoritative; in-process subscribers for same-process handlers."""

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from schemas.common import new_id

EVENT_TYPES = [
    "business.created",
    "business.updated",
    "metric.created",
    "metric.updated",
    "diagnostic.started",
    "diagnostic.completed",
    "research.started",
    "research.completed",
    "competitor.research.started",
    "competitor.research.completed",
    "forecast.created",
    "report.created",
    "report.updated",
    "qa.started",
    "qa.completed",
    "agent.failed",
    "approval.required",
    "approval.granted",
    "approval.rejected",
    "mission.created",
    "mission.started",
    "mission.planned",
    "mission.completed",
    "mission.failed",
    "mission.cancelled",
    "mission.paused",
    "task.started",
    "task.completed",
    "task.failed",
    "conflict.detected",
    "plan.changed",
]


class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        # Non-authoritative recent buffer for same-process consumers
        self._recent: List[Dict[str, Any]] = []

    def subscribe(self, event_type: str, handler: Callable) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    def publish(
        self,
        event_type: str,
        payload: Dict[str, Any],
        organisation_id: str = "",
        *,
        aggregate_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        task_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        event = {
            "event_id": new_id("EVT-"),
            "event_type": event_type,
            "organisation_id": organisation_id or payload.get("organisation_id", ""),
            "payload": payload,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "aggregate_id": aggregate_id or payload.get("mission_id") or payload.get("aggregate_id"),
            "workflow_id": workflow_id or payload.get("mission_id") or payload.get("workflow_id"),
            "task_id": task_id or payload.get("task_id"),
            "correlation_id": correlation_id or payload.get("correlation_id"),
            "causation_id": causation_id,
        }
        self._recent.append(event)
        if len(self._recent) > 500:
            self._recent = self._recent[-500:]

        # Durable write
        org = event["organisation_id"] or "default-org"
        try:
            from persistence.unit_of_work import UnitOfWork

            with UnitOfWork() as uow:
                uow.events.publish(
                    organisation_id=org,
                    event_type=event_type,
                    payload=payload,
                    aggregate_id=event.get("aggregate_id"),
                    workflow_id=event.get("workflow_id"),
                    task_id=event.get("task_id"),
                    correlation_id=event.get("correlation_id"),
                    causation_id=causation_id,
                    event_id=event["event_id"],
                )
        except Exception:
            # Surface persistence failure after local fan-out
            for handler in self._subscribers.get(event_type, []):
                try:
                    handler(event)
                except Exception:
                    pass
            for handler in self._subscribers.get("*", []):
                try:
                    handler(event)
                except Exception:
                    pass
            raise

        for handler in self._subscribers.get(event_type, []):
            try:
                handler(event)
            except Exception:
                pass
        for handler in self._subscribers.get("*", []):
            try:
                handler(event)
            except Exception:
                pass
        return event

    def history(
        self,
        event_type: str = None,
        limit: int = 50,
        organisation_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if organisation_id:
            try:
                from persistence.unit_of_work import UnitOfWork

                with UnitOfWork() as uow:
                    rows = uow.events.list_for_org(
                        organisation_id, event_type=event_type, limit=limit
                    )
                    return [
                        {
                            "event_id": r.event_id,
                            "event_type": r.event_type,
                            "organisation_id": r.organisation_id,
                            "payload": r.payload,
                            "created_at": r.created_at.isoformat() if r.created_at else None,
                            "aggregate_id": r.aggregate_id,
                            "workflow_id": r.workflow_id,
                            "task_id": r.task_id,
                            "correlation_id": r.correlation_id,
                        }
                        for r in rows
                    ]
            except Exception:
                pass
        items = self._recent
        if event_type:
            items = [e for e in items if e["event_type"] == event_type]
        return items[-limit:]


bus = EventBus()
