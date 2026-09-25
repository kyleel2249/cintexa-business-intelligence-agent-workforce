"""Event bus — allows future CINTEXA departments to subscribe."""

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List

from schemas.common import new_id

# Well-known event types
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
]


class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._history: List[Dict[str, Any]] = []

    def subscribe(self, event_type: str, handler: Callable) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    def publish(
        self,
        event_type: str,
        payload: Dict[str, Any],
        organisation_id: str = "",
    ) -> Dict[str, Any]:
        event = {
            "event_id": new_id("EVT-"),
            "event_type": event_type,
            "organisation_id": organisation_id,
            "payload": payload,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._history.append(event)
        for handler in self._subscribers.get(event_type, []):
            try:
                handler(event)
            except Exception:
                pass  # production: log and continue
        for handler in self._subscribers.get("*", []):
            try:
                handler(event)
            except Exception:
                pass
        return event

    def history(self, event_type: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        items = self._history
        if event_type:
            items = [e for e in items if e["event_type"] == event_type]
        return items[-limit:]


# Singleton for the process
bus = EventBus()
