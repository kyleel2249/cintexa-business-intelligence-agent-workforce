"""Shared production coordination tables."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    JSON,
    Index,
    UniqueConstraint,
)

from database.models import Base


class PlatformLease(Base):
    __tablename__ = "plat_leases"
    lease_id = Column(String(64), primary_key=True)
    resource = Column(String(256), nullable=False, index=True)
    owner = Column(String(128), nullable=False)
    fencing_token = Column(Integer, default=1)
    expires_at = Column(DateTime, nullable=False, index=True)
    renewed_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(32), default="ACTIVE")  # ACTIVE|RELEASED|EXPIRED
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("resource", name="uq_plat_lease_resource"),)


class PlatformWorker(Base):
    __tablename__ = "plat_workers"
    worker_id = Column(String(64), primary_key=True)
    hostname = Column(String(256), default="")
    status = Column(String(32), default="ACTIVE")  # ACTIVE|DRAINING|DEAD
    last_heartbeat = Column(DateTime, default=datetime.utcnow)
    capabilities = Column(JSON, default=list)
    meta = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class PlatformJob(Base):
    __tablename__ = "plat_jobs"
    job_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=True, index=True)
    queue = Column(String(64), default="default", index=True)
    job_type = Column(String(128), nullable=False)
    payload = Column(JSON, default=dict)
    status = Column(String(32), default="PENDING", index=True)  # PENDING|CLAIMED|RUNNING|SUCCEEDED|FAILED|DEAD
    priority = Column(Integer, default=100)
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=5)
    owner = Column(String(128), nullable=True)
    lease_expires_at = Column(DateTime, nullable=True)
    visibility_timeout_sec = Column(Integer, default=60)
    error = Column(Text, nullable=True)
    result = Column(JSON, default=dict)
    idempotency_key = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_plat_job_claim", "queue", "status", "priority", "created_at"),
        Index("ix_plat_job_idem", "organisation_id", "idempotency_key"),
    )


class PlatformCircuit(Base):
    __tablename__ = "plat_circuits"
    name = Column(String(128), primary_key=True)
    state = Column(String(32), default="CLOSED")
    failure_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    opened_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    meta = Column(JSON, default=dict)


class PlatformHealth(Base):
    __tablename__ = "plat_health"
    name = Column(String(128), primary_key=True)
    status = Column(String(32), default="UNKNOWN")
    consecutive_failures = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    latency_ms_ema = Column(Float, default=0.0)
    last_success_at = Column(DateTime, nullable=True)
    last_failure_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    meta = Column(JSON, default=dict)


class PlatformFreeze(Base):
    __tablename__ = "plat_freeze"
    id = Column(String(32), primary_key=True, default="global")
    frozen = Column(Boolean, default=False)
    emergency_stop = Column(Boolean, default=False)
    reason = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String(128), default="")


class PlatformCanaryRoute(Base):
    """Actual traffic routing policy for canaries."""
    __tablename__ = "plat_canary_routes"
    route_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    capability = Column(String(128), nullable=False, index=True)  # e.g. agent:research, model:chat
    baseline_version = Column(String(64), nullable=False)
    candidate_version = Column(String(64), nullable=False)
    percent = Column(Integer, default=0)  # 0-100 candidate share
    status = Column(String(32), default="ACTIVE")  # ACTIVE|PAUSED|ROLLED_BACK
    release_id = Column(String(64), nullable=True)
    sticky = Column(Boolean, default=False)
    meta = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (Index("ix_plat_canary_org_cap", "organisation_id", "capability"),)


class PlatformIdempotency(Base):
    __tablename__ = "plat_idempotency"
    key = Column(String(256), primary_key=True)
    organisation_id = Column(String(64), nullable=True, index=True)
    response = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
