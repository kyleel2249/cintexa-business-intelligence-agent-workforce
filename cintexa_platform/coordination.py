"""Durable circuit, health, freeze — multi-worker coherent."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from persistence.unit_of_work import UnitOfWork
from cintexa_platform.models_db import PlatformCircuit, PlatformFreeze, PlatformHealth


class DurableCircuit:
    def __init__(self, name: str, failure_threshold: int = 5, cooldown_sec: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_sec = cooldown_sec

    def _row(self, uow) -> PlatformCircuit:
        row = uow.session.get(PlatformCircuit, self.name)
        if not row:
            row = PlatformCircuit(name=self.name, state="CLOSED")
            uow.session.add(row)
            uow.session.flush()
        return row

    def allow(self) -> bool:
        with UnitOfWork() as uow:
            row = self._row(uow)
            if row.state == "CLOSED":
                return True
            if row.state == "OPEN":
                if row.opened_at and (datetime.utcnow() - row.opened_at).total_seconds() >= self.cooldown_sec:
                    row.state = "HALF_OPEN"
                    row.updated_at = datetime.utcnow()
                    return True
                return False
            return True  # HALF_OPEN trial

    def record_success(self) -> None:
        with UnitOfWork() as uow:
            row = self._row(uow)
            row.success_count = (row.success_count or 0) + 1
            if row.state == "HALF_OPEN":
                row.state = "CLOSED"
                row.failure_count = 0
            row.updated_at = datetime.utcnow()

    def record_failure(self) -> None:
        with UnitOfWork() as uow:
            row = self._row(uow)
            row.failure_count = (row.failure_count or 0) + 1
            row.updated_at = datetime.utcnow()
            if row.state == "HALF_OPEN" or row.failure_count >= self.failure_threshold:
                row.state = "OPEN"
                row.opened_at = datetime.utcnow()

    def status(self) -> dict:
        with UnitOfWork() as uow:
            row = self._row(uow)
            return {"name": row.name, "state": row.state, "failure_count": row.failure_count}


class DurableHealth:
    def record_success(self, name: str, latency_ms: float = 0.0) -> None:
        with UnitOfWork() as uow:
            row = uow.session.get(PlatformHealth, name)
            if not row:
                row = PlatformHealth(name=name)
                uow.session.add(row)
            row.consecutive_failures = 0
            row.success_count = (row.success_count or 0) + 1
            row.status = "HEALTHY"
            row.last_success_at = datetime.utcnow()
            if latency_ms:
                row.latency_ms_ema = (
                    latency_ms if not row.latency_ms_ema else 0.8 * row.latency_ms_ema + 0.2 * latency_ms
                )
            row.updated_at = datetime.utcnow()

    def record_failure(self, name: str) -> None:
        with UnitOfWork() as uow:
            row = uow.session.get(PlatformHealth, name)
            if not row:
                row = PlatformHealth(name=name)
                uow.session.add(row)
            row.consecutive_failures = (row.consecutive_failures or 0) + 1
            row.failure_count = (row.failure_count or 0) + 1
            row.last_failure_at = datetime.utcnow()
            if row.consecutive_failures >= 5:
                row.status = "UNAVAILABLE"
            elif row.consecutive_failures >= 2:
                row.status = "DEGRADED"
            row.updated_at = datetime.utcnow()

    def get(self, name: str) -> dict:
        with UnitOfWork() as uow:
            row = uow.session.get(PlatformHealth, name)
            if not row:
                return {"name": name, "status": "UNKNOWN"}
            return {
                "name": row.name,
                "status": row.status,
                "consecutive_failures": row.consecutive_failures,
                "latency_ms_ema": row.latency_ms_ema,
            }


class DurableFreeze:
    def _ensure(self, uow) -> PlatformFreeze:
        row = uow.session.get(PlatformFreeze, "global")
        if not row:
            row = PlatformFreeze(id="global", frozen=False, emergency_stop=False)
            uow.session.add(row)
            uow.session.flush()
        return row

    def status(self) -> dict:
        with UnitOfWork() as uow:
            row = self._ensure(uow)
            return {
                "frozen": bool(row.frozen),
                "emergency_stop": bool(row.emergency_stop),
                "reason": row.reason or "",
            }

    def freeze(self, reason: str = "", by: str = "") -> dict:
        with UnitOfWork() as uow:
            row = self._ensure(uow)
            row.frozen = True
            row.reason = reason
            row.updated_by = by
            row.updated_at = datetime.utcnow()
        return self.status()

    def unfreeze(self, by: str = "") -> dict:
        with UnitOfWork() as uow:
            row = self._ensure(uow)
            if row.emergency_stop:
                from core.errors import AuthorizationError
                raise AuthorizationError("Clear emergency stop first")
            row.frozen = False
            row.reason = ""
            row.updated_by = by
        return self.status()

    def emergency(self, reason: str = "", by: str = "") -> dict:
        with UnitOfWork() as uow:
            row = self._ensure(uow)
            row.emergency_stop = True
            row.frozen = True
            row.reason = reason
            row.updated_by = by
        return self.status()

    def clear_emergency(self, *, authorized: bool, by: str = "") -> dict:
        if not authorized:
            from core.errors import AuthorizationError
            raise AuthorizationError("Authorization required")
        with UnitOfWork() as uow:
            row = self._ensure(uow)
            row.emergency_stop = False
            row.frozen = False
            row.reason = ""
            row.updated_by = by
        return self.status()
