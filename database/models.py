"""SQLAlchemy models — organisation-isolated schema for CINTEXA BI."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Organisation(Base):
    __tablename__ = "organisations"
    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    users = relationship("User", back_populates="organisation")


class User(Base):
    __tablename__ = "users"
    id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(64), default="member")  # admin | member | viewer
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    organisation = relationship("Organisation", back_populates="users")


class AgentRecord(Base):
    __tablename__ = "agents"
    agent_id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    role = Column(String(255))
    enabled = Column(Boolean, default=True)
    version = Column(String(32), default="1.0.0")
    config = Column(JSON, default=dict)


class AgentTask(Base):
    __tablename__ = "agent_tasks"
    task_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=False)
    request = Column(Text, nullable=False)
    objective = Column(String(255))
    state = Column(String(32), default="PENDING", index=True)
    priority = Column(String(16), default="medium")
    plan = Column(JSON)
    results = Column(JSON, default=dict)
    evidence_ids = Column(JSON, default=list)
    errors = Column(JSON, default=list)
    requires_human_approval = Column(Boolean, default=False)
    approval_status = Column(String(32))
    context = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime)
    completed_at = Column(DateTime)

    __table_args__ = (Index("ix_tasks_org_state", "organisation_id", "state"),)


class AgentMessageRecord(Base):
    __tablename__ = "agent_messages"
    message_id = Column(String(64), primary_key=True)
    task_id = Column(String(64), nullable=False, index=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    from_agent = Column(String(64))
    to_agent = Column(String(64))
    message_type = Column(String(32))
    priority = Column(String(16))
    data = Column(JSON)
    evidence_ids = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentRun(Base):
    __tablename__ = "agent_runs"
    run_id = Column(String(64), primary_key=True)
    agent_id = Column(String(64), nullable=False, index=True)
    task_id = Column(String(64), nullable=False, index=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    status = Column(String(32))
    tools_used = Column(JSON, default=list)
    evidence_ids = Column(JSON, default=list)
    errors = Column(JSON, default=list)
    retries = Column(Integer, default=0)
    duration_ms = Column(Integer)
    qa_result = Column(String(32))
    started_at = Column(DateTime)
    completed_at = Column(DateTime)


class BusinessProfile(Base):
    __tablename__ = "business_profiles"
    id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    name = Column(String(255))
    industry = Column(String(255))
    geography = Column(String(255))
    data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime)


class BusinessMetric(Base):
    __tablename__ = "business_metrics"
    id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    value = Column(Float)
    period = Column(String(64))
    source = Column(String(255))
    calculation_method = Column(String(255))
    confidence = Column(String(32))
    meta = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class BusinessDiagnostic(Base):
    __tablename__ = "business_diagnostics"
    diagnostic_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    task_id = Column(String(64))
    overall_score = Column(Float)
    report = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class EvidenceRecord(Base):
    __tablename__ = "evidence"
    evidence_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    claim = Column(Text)
    source = Column(String(1024))
    source_type = Column(String(64))
    published_date = Column(String(32))
    retrieved_date = Column(String(32))
    confidence = Column(Float)
    classification = Column(String(32))
    source_quality = Column(String(8))
    supports = Column(JSON, default=list)
    meta = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"
    knowledge_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    title = Column(String(512))
    content = Column(Text)
    source = Column(String(1024))
    category = Column(String(128))
    owner = Column(String(128))
    confidence = Column(Float)
    version = Column(Integer, default=1)
    review_date = Column(String(32))
    permissions = Column(JSON, default=list)
    tags = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime)


class MemoryItem(Base):
    __tablename__ = "memory_items"
    memory_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    category = Column(String(32), nullable=False)  # short_term | working | long_term | user_provided | derived
    content = Column(JSON)
    source = Column(String(255))
    task_id = Column(String(64))
    permissions = Column(JSON, default=list)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)


class ReportRecord(Base):
    __tablename__ = "reports"
    report_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    task_id = Column(String(64))
    report_type = Column(String(64))
    title = Column(String(512))
    format = Column(String(16))  # html | markdown | pdf | docx | json
    content = Column(Text)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)


class QualityReview(Base):
    __tablename__ = "quality_reviews"
    review_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    task_id = Column(String(64), nullable=False)
    qa_result = Column(String(32))
    reasons = Column(JSON, default=list)
    checks_passed = Column(JSON, default=list)
    checks_failed = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    log_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    actor = Column(String(128))
    action = Column(String(128))
    resource_type = Column(String(64))
    resource_id = Column(String(64))
    details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class EventRecord(Base):
    __tablename__ = "events"
    event_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), index=True)
    event_type = Column(String(128), nullable=False, index=True)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
