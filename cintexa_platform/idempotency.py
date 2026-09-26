"""Write-path idempotency store."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from persistence.unit_of_work import UnitOfWork
from cintexa_platform.models_db import PlatformIdempotency


class IdempotencyStore:
    def get(self, key: str, organisation_id: Optional[str] = None) -> Optional[Dict]:
        with UnitOfWork() as uow:
            row = uow.session.get(PlatformIdempotency, key)
            if not row:
                return None
            if organisation_id and row.organisation_id and row.organisation_id != organisation_id:
                return None
            if row.expires_at and row.expires_at < datetime.utcnow():
                return None
            return row.response or {}

    def put(
        self,
        key: str,
        response: Dict[str, Any],
        *,
        organisation_id: Optional[str] = None,
        ttl_sec: int = 86400,
    ) -> None:
        with UnitOfWork() as uow:
            existing = uow.session.get(PlatformIdempotency, key)
            expires = datetime.utcnow() + timedelta(seconds=ttl_sec)
            if existing:
                existing.response = response
                existing.expires_at = expires
                existing.organisation_id = organisation_id
            else:
                uow.session.add(
                    PlatformIdempotency(
                        key=key,
                        organisation_id=organisation_id,
                        response=response,
                        expires_at=expires,
                    )
                )
