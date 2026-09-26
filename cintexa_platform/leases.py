"""Distributed leases with fencing tokens."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from core.errors import AuthorizationError, ConflictError
from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from cintexa_platform.models_db import PlatformLease


class LeaseService:
    def acquire(self, resource: str, owner: str, *, ttl_sec: int = 30) -> dict:
        now = datetime.utcnow()
        expires = now + timedelta(seconds=ttl_sec)
        with UnitOfWork() as uow:
            row = uow.session.query(PlatformLease).filter_by(resource=resource).one_or_none()
            if row and row.status == "ACTIVE" and row.expires_at > now and row.owner != owner:
                raise ConflictError(f"Lease held by {row.owner}")
            if row:
                row.owner = owner
                row.fencing_token = (row.fencing_token or 0) + 1
                row.expires_at = expires
                row.renewed_at = now
                row.status = "ACTIVE"
                lease_id = row.lease_id
                token = row.fencing_token
            else:
                lease_id = new_id("LSE-")
                token = 1
                uow.session.add(
                    PlatformLease(
                        lease_id=lease_id,
                        resource=resource,
                        owner=owner,
                        fencing_token=token,
                        expires_at=expires,
                        status="ACTIVE",
                    )
                )
        return {"lease_id": lease_id, "resource": resource, "owner": owner, "fencing_token": token, "expires_at": expires.isoformat()}

    def renew(self, resource: str, owner: str, fencing_token: int, *, ttl_sec: int = 30) -> dict:
        now = datetime.utcnow()
        with UnitOfWork() as uow:
            row = uow.session.query(PlatformLease).filter_by(resource=resource).one_or_none()
            if not row or row.owner != owner or row.fencing_token != fencing_token:
                raise AuthorizationError("Stale or invalid lease — fencing token mismatch")
            if row.status != "ACTIVE":
                raise AuthorizationError("Lease not active")
            row.expires_at = now + timedelta(seconds=ttl_sec)
            row.renewed_at = now
        return {"resource": resource, "renewed": True, "fencing_token": fencing_token}

    def release(self, resource: str, owner: str, fencing_token: int) -> dict:
        with UnitOfWork() as uow:
            row = uow.session.query(PlatformLease).filter_by(resource=resource).one_or_none()
            if not row:
                return {"released": True}
            if row.owner != owner or row.fencing_token != fencing_token:
                raise AuthorizationError("Cannot release — fencing token mismatch")
            row.status = "RELEASED"
        return {"released": True}

    def expire_stale(self) -> int:
        now = datetime.utcnow()
        n = 0
        with UnitOfWork() as uow:
            rows = uow.session.query(PlatformLease).filter(
                PlatformLease.status == "ACTIVE",
                PlatformLease.expires_at < now,
            ).all()
            for r in rows:
                r.status = "EXPIRED"
                n += 1
        return n
