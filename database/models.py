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


# ── Workforce Orchestrator persistence ──────────────────────────

class MissionRecord(Base):
    __tablename__ = "missions"
    mission_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    workspace_id = Column(String(64), default="default-workspace", index=True)
    user_id = Column(String(64), nullable=False, index=True)
    objective = Column(Text, default="")
    original_request = Column(Text, default="")
    status = Column(String(32), default="CREATED", index=True)
    priority = Column(String(16), default="NORMAL")
    business_domain = Column(String(64), default="general")
    plan_version = Column(Integer, default=0)
    confidence = Column(Float, default=0.0)
    quality_score = Column(Float, default=0.0)
    idempotency_key = Column(String(128), nullable=True, index=True)
    payload = Column(JSON, default=dict)  # full mission dump
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_missions_org_status", "organisation_id", "status"),
    )


class MissionEventRecord(Base):
    __tablename__ = "mission_events"
    event_id = Column(String(64), primary_key=True)
    mission_id = Column(String(64), nullable=False, index=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class OrchestrationDecisionRecord(Base):
    __tablename__ = "orchestration_decisions"
    decision_id = Column(String(64), primary_key=True)
    mission_id = Column(String(64), nullable=False, index=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    decision_type = Column(String(64), nullable=False)
    decision = Column(Text, default="")
    reason = Column(Text, default="")
    selected_option = Column(String(255), default="")
    confidence = Column(Float, default=0.0)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Phase 1 durable foundation extensions ───────────────────────

class Membership(Base):
    """User ↔ Organisation membership with role (multi-tenant boundary)."""
    __tablename__ = "memberships"
    id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), ForeignKey("organisations.id"), nullable=False, index=True)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(64), default="member")  # owner | admin | member | viewer
    status = Column(String(32), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_memberships_org_user", "organisation_id", "user_id", unique=True),
    )


class WorkflowRecord(Base):
    """Durable workflow / mission execution state."""
    __tablename__ = "workflows"
    workflow_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    workflow_type = Column(String(64), default="mission")
    objective = Column(Text, default="")
    status = Column(String(32), default="CREATED", index=True)
    current_state = Column(String(64), default="")
    checkpoint_id = Column(String(64), nullable=True)
    result = Column(JSON, default=dict)
    error = Column(Text, nullable=True)
    priority = Column(String(16), default="NORMAL")
    version = Column(Integer, default=1)  # optimistic concurrency
    idempotency_key = Column(String(128), nullable=True, index=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_workflows_org_status", "organisation_id", "status"),
        Index("ix_workflows_org_idem", "organisation_id", "idempotency_key"),
    )


class WorkflowStepRecord(Base):
    __tablename__ = "workflow_steps"
    step_id = Column(String(64), primary_key=True)
    workflow_id = Column(String(64), nullable=False, index=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    task_id = Column(String(64), nullable=True, index=True)
    sequence = Column(Integer, default=0)
    objective = Column(Text, default="")
    status = Column(String(32), default="PENDING", index=True)
    dependencies = Column(JSON, default=list)
    assigned_agent = Column(String(64), nullable=True)
    result = Column(JSON, default=dict)
    error = Column(Text, nullable=True)
    execution_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_workflow_steps_wf_seq", "workflow_id", "sequence"),
    )


class CheckpointRecord(Base):
    __tablename__ = "checkpoints"
    checkpoint_id = Column(String(64), primary_key=True)
    workflow_id = Column(String(64), nullable=False, index=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    current_step = Column(String(64), nullable=True)
    completed_steps = Column(JSON, default=list)
    pending_steps = Column(JSON, default=list)
    state_refs = Column(JSON, default=dict)
    execution_metadata = Column(JSON, default=dict)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_checkpoints_wf", "workflow_id", "version"),
    )


class ConversationRecord(Base):
    __tablename__ = "conversations"
    session_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    title = Column(String(255), default="New chat")
    messages = Column(JSON, default=list)
    mission_id = Column(String(64), nullable=True, index=True)
    status = Column(String(32), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_conversations_org_user", "organisation_id", "user_id"),
    )


class MemoryRecord(Base):
    __tablename__ = "memories"
    memory_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(64), nullable=True, index=True)
    memory_type = Column(String(64), default="working", index=True)  # short_term|working|long_term|user_provided|derived
    content = Column(JSON, default=dict)
    source = Column(String(128), default="agent")
    source_ref = Column(String(128), nullable=True)
    task_id = Column(String(64), nullable=True, index=True)
    mission_id = Column(String(64), nullable=True, index=True)
    status = Column(String(32), default="active")
    metadata_json = Column(JSON, default=dict)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_memories_org_type", "organisation_id", "memory_type"),
    )


class DurableEvent(Base):
    """Durable event log (Phase 1 foundation for streaming in later phases)."""
    __tablename__ = "durable_events"
    event_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    event_type = Column(String(128), nullable=False, index=True)
    aggregate_id = Column(String(64), nullable=True, index=True)
    workflow_id = Column(String(64), nullable=True, index=True)
    task_id = Column(String(64), nullable=True, index=True)
    payload = Column(JSON, default=dict)
    correlation_id = Column(String(64), nullable=True, index=True)
    causation_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_durable_events_org_type", "organisation_id", "event_type"),
        Index("ix_durable_events_org_created", "organisation_id", "created_at"),
    )


class ArtifactRecord(Base):
    __tablename__ = "artifacts"
    artifact_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    name = Column(String(255), default="")
    artifact_type = Column(String(64), default="file")
    storage_ref = Column(String(512), nullable=True)
    metadata_json = Column(JSON, default=dict)
    task_id = Column(String(64), nullable=True)
    workflow_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
