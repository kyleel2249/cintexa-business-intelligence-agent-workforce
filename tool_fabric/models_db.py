"""Phase 4 Tool Fabric durable schema."""

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


class TFTool(Base):
    __tablename__ = "tf_tools"
    tool_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)  # __system__ for global
    name = Column(String(128), nullable=False)
    slug = Column(String(128), nullable=False, index=True)
    description = Column(Text, default="")
    version = Column(String(32), default="1.0.0")
    category = Column(String(64), nullable=False, index=True)
    capabilities = Column(JSON, default=list)
    input_schema = Column(JSON, default=dict)
    output_schema = Column(JSON, default=dict)
    permissions = Column(JSON, default=list)
    risk = Column(String(32), default="low")  # low|medium|high|critical
    requires_approval = Column(Boolean, default=False)
    enabled = Column(Boolean, default=True)
    timeout_sec = Column(Integer, default=30)
    max_output_bytes = Column(Integer, default=1_000_000)
    config = Column(JSON, default=dict)
    health_score = Column(Float, default=1.0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organisation_id", "slug", "version", name="uq_tf_tool_ver"),
        Index("ix_tf_tools_org_cat", "organisation_id", "category"),
    )


class TFExecution(Base):
    __tablename__ = "tf_executions"
    execution_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    tool_id = Column(String(64), nullable=False, index=True)
    tool_slug = Column(String(128), nullable=False)
    tool_version = Column(String(32), nullable=False)
    requester = Column(String(128), nullable=True)
    user_id = Column(String(64), nullable=True)
    agent_key = Column(String(128), nullable=True)
    task_id = Column(String(64), nullable=True, index=True)
    workflow_id = Column(String(64), nullable=True, index=True)
    correlation_id = Column(String(64), nullable=True, index=True)
    status = Column(String(32), default="REQUESTED", index=True)
    # REQUESTED|AUTHORIZED|DENIED|PENDING_APPROVAL|RUNNING|COMPLETED|FAILED|CANCELLED|TIMED_OUT
    input_json = Column(JSON, default=dict)
    result_json = Column(JSON, default=dict)
    error = Column(Text, nullable=True)
    policy_snapshot = Column(JSON, default=dict)
    dry_run = Column(Boolean, default=False)
    workspace_path = Column(String(1024), nullable=True)
    latency_ms = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_tf_exec_org_status", "organisation_id", "status"),)


class TFArtifact(Base):
    __tablename__ = "tf_artifacts"
    artifact_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    execution_id = Column(String(64), nullable=True, index=True)
    task_id = Column(String(64), nullable=True)
    workflow_id = Column(String(64), nullable=True)
    tool_slug = Column(String(128), nullable=True)
    name = Column(String(512), default="")
    mime_type = Column(String(128), default="application/octet-stream")
    size_bytes = Column(Integer, default=0)
    checksum = Column(String(128), nullable=True)
    storage_ref = Column(String(1024), nullable=True)  # path or URI
    permissions = Column(JSON, default=list)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_tf_art_org", "organisation_id"),)


class TFApproval(Base):
    __tablename__ = "tf_approvals"
    approval_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    execution_id = Column(String(64), nullable=False, index=True)
    status = Column(String(32), default="PENDING_APPROVAL")  # PENDING_APPROVAL|APPROVED|REJECTED|EXPIRED|CANCELLED
    reason = Column(Text, default="")
    requested_by = Column(String(128), nullable=True)
    decided_by = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    decided_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)


class TFPolicy(Base):
    __tablename__ = "tf_policies"
    policy_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    allowed_tools = Column(JSON, default=list)
    denied_tools = Column(JSON, default=list)
    allowed_commands = Column(JSON, default=list)
    denied_commands = Column(JSON, default=list)
    allowed_dirs = Column(JSON, default=list)
    network_mode = Column(String(32), default="deny")  # deny|allowlist|allow
    allowed_domains = Column(JSON, default=list)
    max_timeout_sec = Column(Integer, default=60)
    max_output_bytes = Column(Integer, default=1_000_000)
    max_memory_mb = Column(Integer, default=512)
    config = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
