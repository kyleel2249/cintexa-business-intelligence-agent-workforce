"""External interaction kill switches — durable."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from persistence.unit_of_work import UnitOfWork
from external_fabric.models_db import ExtKillSwitch


class ExternalKillSwitch:
    def status(self, organisation_id: Optional[str] = None) -> dict:
        with UnitOfWork() as uow:
            global_row = uow.session.get(ExtKillSwitch, "global")
            org_row = uow.session.get(ExtKillSwitch, f"org:{organisation_id}") if organisation_id else None
            g = bool(global_row and global_row.writes_blocked)
            o = bool(org_row and org_row.writes_blocked)
            return {
                "global_writes_blocked": g,
                "org_writes_blocked": o,
                "writes_blocked": g or o,
                "reason": (org_row.reason if org_row and org_row.writes_blocked else None)
                or (global_row.reason if global_row else ""),
            }

    def writes_blocked(self, organisation_id: Optional[str] = None) -> bool:
        return self.status(organisation_id)["writes_blocked"]

    def activate(self, *, scope: str = "global", organisation_id: Optional[str] = None, reason: str = "") -> dict:
        key = "global" if scope == "global" else f"org:{organisation_id}"
        with UnitOfWork() as uow:
            row = uow.session.get(ExtKillSwitch, key)
            if not row:
                row = ExtKillSwitch(id=key, writes_blocked=True, reason=reason)
                uow.session.add(row)
            else:
                row.writes_blocked = True
                row.reason = reason
                row.updated_at = datetime.utcnow()
        return self.status(organisation_id)

    def deactivate(self, *, scope: str = "global", organisation_id: Optional[str] = None, authorized: bool = False) -> dict:
        if not authorized:
            from core.errors import AuthorizationError
            raise AuthorizationError("Kill switch deactivation requires authorization")
        key = "global" if scope == "global" else f"org:{organisation_id}"
        with UnitOfWork() as uow:
            row = uow.session.get(ExtKillSwitch, key)
            if row:
                row.writes_blocked = False
                row.reason = ""
                row.updated_at = datetime.utcnow()
        return self.status(organisation_id)
