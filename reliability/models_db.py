"""Durable reliability state."""

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
)

from database.models import Base


class RelRetryRecord(Base):
    __tablename__ = "rel_retry_records"
    record_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    correlation_id = Column(String(64), nullable=True, index=True)
    scope_key = Column(String(128), default="")
    attempt = Column(Integer, default=1)
    category = Column(String(64), nullable=True)
    success = Column(Boolean, default=False)
    error = Column(Text, nullable=True)
    delay_sec = Column(Float, default=0.0)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_rel_retry_org", "organisation_id", "correlation_id"),)


class RelDeadLetter(Base):
    __tablename__ = "rel_dead_letters"
    dead_letter_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    source_type = Column(String(64), default="execution")  # execution|task|workflow|event
    source_id = Column(String(64), nullable=True, index=True)
    correlation_id = Column(String(64), nullable=True)
    category = Column(String(64), nullable=True)
    reason = Column(Text, default="")
    attempts = Column(Integer, default=0)
    history = Column(JSON, default=list)
    payload = Column(JSON, default=dict)
    status = Column(String(32), default="OPEN")  # OPEN|REPROCESSING|CLOSED|CANCELLED
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (Index("ix_rel_dl_org_status", "organisation_id", "status"),)


class RelCircuitState(Base):
    __tablename__ = "rel_circuit_states"
    circuit_id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False, unique=True, index=True)
    state = Column(String(32), default="CLOSED")
    failure_count = Column(Integer, default=0)
    opened_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RelCompensation(Base):
    __tablename__ = "rel_compensations"
    compensation_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    workflow_id = Column(String(64), nullable=True, index=True)
    step_id = Column(String(64), nullable=True)
    status = Column(String(32), default="PENDING")  # PENDING|STARTED|COMPLETED|FAILED
    forward_op = Column(String(128), default="")
    compensation_op = Column(String(128), default="")
    payload = Column(JSON, default=dict)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class RelOutbox(Base):
    __tablename__ = "rel_outbox"
    outbox_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=True, index=True)
    event_type = Column(String(128), nullable=False)
    payload = Column(JSON, default=dict)
    published = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)

    __table_args__ = (Index("ix_rel_outbox_pub", "published", "created_at"),)


class RelProcessedEvent(Base):
    """Inbox — consumers mark event IDs as processed for at-least-once tolerance."""
    __tablename__ = "rel_processed_events"
    id = Column(String(64), primary_key=True)
    consumer = Column(String(128), nullable=False)
    event_id = Column(String(64), nullable=False)
    processed_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_rel_inbox_unique", "consumer", "event_id", unique=True),)
