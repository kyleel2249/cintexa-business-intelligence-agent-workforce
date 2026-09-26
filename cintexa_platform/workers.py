"""Worker registration, heartbeat, job queue with claim/lease."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from core.errors import ConflictError, ValidationError
from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from cintexa_platform.models_db import PlatformJob, PlatformWorker


class WorkerRegistry:
    def register(self, worker_id: str, *, hostname: str = "", capabilities: Optional[List] = None) -> dict:
        with UnitOfWork() as uow:
            row = uow.session.get(PlatformWorker, worker_id)
            if row:
                row.status = "ACTIVE"
                row.last_heartbeat = datetime.utcnow()
                row.hostname = hostname or row.hostname
                row.capabilities = capabilities or row.capabilities or []
            else:
                uow.session.add(
                    PlatformWorker(
                        worker_id=worker_id,
                        hostname=hostname,
                        status="ACTIVE",
                        capabilities=capabilities or [],
                    )
                )
        return {"worker_id": worker_id, "status": "ACTIVE"}

    def heartbeat(self, worker_id: str) -> dict:
        with UnitOfWork() as uow:
            row = uow.session.get(PlatformWorker, worker_id)
            if not row:
                raise ValidationError("Worker not registered")
            row.last_heartbeat = datetime.utcnow()
            if row.status == "DEAD":
                row.status = "ACTIVE"
        return {"worker_id": worker_id, "heartbeat": True}

    def drain(self, worker_id: str) -> dict:
        with UnitOfWork() as uow:
            row = uow.session.get(PlatformWorker, worker_id)
            if row:
                row.status = "DRAINING"
        return {"worker_id": worker_id, "status": "DRAINING"}

    def mark_stale(self, *, timeout_sec: int = 90) -> int:
        cutoff = datetime.utcnow() - timedelta(seconds=timeout_sec)
        n = 0
        with UnitOfWork() as uow:
            rows = uow.session.query(PlatformWorker).filter(
                PlatformWorker.status == "ACTIVE",
                PlatformWorker.last_heartbeat < cutoff,
            ).all()
            for r in rows:
                r.status = "DEAD"
                n += 1
        return n


class JobQueue:
    def enqueue(
        self,
        job_type: str,
        payload: Dict[str, Any],
        *,
        organisation_id: Optional[str] = None,
        queue: str = "default",
        priority: int = 100,
        max_attempts: int = 5,
        idempotency_key: Optional[str] = None,
    ) -> dict:
        if idempotency_key and organisation_id:
            with UnitOfWork() as uow:
                existing = (
                    uow.session.query(PlatformJob)
                    .filter_by(organisation_id=organisation_id, idempotency_key=idempotency_key)
                    .order_by(PlatformJob.created_at.desc())
                    .first()
                )
                if existing:
                    return {"job_id": existing.job_id, "status": existing.status, "deduped": True}

        jid = new_id("JOB-")
        with UnitOfWork() as uow:
            uow.session.add(
                PlatformJob(
                    job_id=jid,
                    organisation_id=organisation_id,
                    queue=queue,
                    job_type=job_type,
                    payload=payload,
                    status="PENDING",
                    priority=priority,
                    max_attempts=max_attempts,
                    idempotency_key=idempotency_key,
                )
            )
        return {"job_id": jid, "status": "PENDING", "deduped": False}

    def claim(self, worker_id: str, *, queue: str = "default", visibility_timeout_sec: int = 60) -> Optional[dict]:
        """Atomic claim: select candidate then UPDATE ... WHERE status still claimable."""
        now = datetime.utcnow()
        lease_until = now + timedelta(seconds=visibility_timeout_sec)
        with UnitOfWork() as uow:
            # Reclaim expired leases back to PENDING
            (
                uow.session.query(PlatformJob)
                .filter(
                    PlatformJob.queue == queue,
                    PlatformJob.status.in_(["CLAIMED", "RUNNING"]),
                    PlatformJob.lease_expires_at != None,  # noqa: E711
                    PlatformJob.lease_expires_at < now,
                )
                .update(
                    {
                        PlatformJob.status: "PENDING",
                        PlatformJob.owner: None,
                        PlatformJob.lease_expires_at: None,
                    },
                    synchronize_session=False,
                )
            )
            uow.session.flush()

            # Try a few candidates under contention
            for _ in range(8):
                job = (
                    uow.session.query(PlatformJob)
                    .filter_by(queue=queue, status="PENDING")
                    .order_by(PlatformJob.priority.asc(), PlatformJob.created_at.asc())
                    .first()
                )
                if not job:
                    return None
                jid = job.job_id
                prev_attempts = job.attempts or 0
                # Atomic conditional claim
                updated = (
                    uow.session.query(PlatformJob)
                    .filter(
                        PlatformJob.job_id == jid,
                        PlatformJob.status == "PENDING",
                    )
                    .update(
                        {
                            PlatformJob.status: "CLAIMED",
                            PlatformJob.owner: worker_id,
                            PlatformJob.attempts: prev_attempts + 1,
                            PlatformJob.lease_expires_at: lease_until,
                            PlatformJob.updated_at: now,
                        },
                        synchronize_session=False,
                    )
                )
                if updated == 1:
                    uow.session.expire_all()
                    job = uow.session.get(PlatformJob, jid)
                    return {
                        "job_id": job.job_id,
                        "job_type": job.job_type,
                        "payload": job.payload or {},
                        "attempts": job.attempts,
                        "organisation_id": job.organisation_id,
                    }
                # lost race — try next
            return None

    def complete(self, job_id: str, worker_id: str, result: Optional[Dict] = None) -> dict:
        with UnitOfWork() as uow:
            job = uow.session.get(PlatformJob, job_id)
            if not job or job.owner != worker_id:
                raise ConflictError("Job not owned by worker")
            job.status = "SUCCEEDED"
            job.result = result or {}
            job.updated_at = datetime.utcnow()
        return {"job_id": job_id, "status": "SUCCEEDED"}

    def fail(self, job_id: str, worker_id: str, error: str) -> dict:
        with UnitOfWork() as uow:
            job = uow.session.get(PlatformJob, job_id)
            if not job or job.owner != worker_id:
                raise ConflictError("Job not owned by worker")
            if job.attempts >= (job.max_attempts or 5):
                job.status = "DEAD"
            else:
                job.status = "PENDING"
                job.owner = None
                job.lease_expires_at = None
            job.error = error[:2000]
            job.updated_at = datetime.utcnow()
            status = job.status
        return {"job_id": job_id, "status": status}
