"""Alerting and SLO foundation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from events.bus import bus
from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from observability.models_db import ObsAlert, ObsIncident
from observability.metrics import metrics


class AlertService:
    def check_error_rate(
        self, organisation_id: str, *, threshold: float = 0.5, window: str = "span.app.error"
    ) -> Optional[Dict]:
        snap = metrics.snapshot(organisation_id)
        errors = snap["counters"].get(f"{metric}|{organisation_id}", 0)
        ok = snap["counters"].get(f"span.app.ok|{organisation_id}", 0)
        total = errors + ok
        rate = errors / total if total else 0.0
        if total >= 3 and rate >= threshold:
            return self.fire(
                organisation_id,
                rule="error_rate",
                severity="WARNING",
                message=f"Error rate {rate:.2f} >= {threshold}",
                value=rate,
                threshold=threshold,
            )
        return None

    def fire(
        self,
        organisation_id: str,
        *,
        rule: str,
        severity: str,
        message: str,
        value: Optional[float] = None,
        threshold: Optional[float] = None,
        related_trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        aid = new_id("ALT-")
        with UnitOfWork() as uow:
            uow.session.add(
                ObsAlert(
                    alert_id=aid,
                    organisation_id=organisation_id,
                    rule=rule,
                    severity=severity,
                    message=message,
                    value=value,
                    threshold=threshold,
                    related_trace_id=related_trace_id,
                )
            )
        bus.publish("alert.fired", {"alert_id": aid, "rule": rule}, organisation_id=organisation_id)
        return {"alert_id": aid, "rule": rule, "severity": severity}

    def list_open(self, organisation_id: str) -> List[dict]:
        with UnitOfWork() as uow:
            rows = (
                uow.session.query(ObsAlert)
                .filter_by(organisation_id=organisation_id, status="OPEN")
                .order_by(ObsAlert.created_at.desc())
                .limit(50)
                .all()
            )
            return [
                {
                    "alert_id": r.alert_id,
                    "rule": r.rule,
                    "severity": r.severity,
                    "message": r.message,
                    "value": r.value,
                    "threshold": r.threshold,
                }
                for r in rows
            ]


class IncidentService:
    def create(
        self, organisation_id: str, title: str, *, severity: str = "MEDIUM", symptoms: str = ""
    ) -> Dict[str, Any]:
        iid = new_id("INC-")
        with UnitOfWork() as uow:
            uow.session.add(
                ObsIncident(
                    incident_id=iid,
                    organisation_id=organisation_id,
                    severity=severity,
                    title=title,
                    symptoms=symptoms,
                )
            )
        return {"incident_id": iid, "status": "OPEN"}
