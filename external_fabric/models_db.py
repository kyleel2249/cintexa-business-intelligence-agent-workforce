"""Durable external interaction models."""

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


class ExtKillSwitch(Base):
    __tablename__ = "ext_kill_switches"
    id = Column(String(64), primary_key=True)
    writes_blocked = Column(Boolean, default=False)
    reason = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ExtBrowserSession(Base):
    __tablename__ = "ext_browser_sessions"
    session_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    agent_id = Column(String(64), nullable=True)
    task_id = Column(String(64), nullable=True)
    workflow_id = Column(String(64), nullable=True)
    provider = Column(String(64), default="mock")
    status = Column(String(32), default="CREATED")
    allowed_domains = Column(JSON, default=list)
    current_url = Column(String(2048), nullable=True)
    meta = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    __table_args__ = (Index("ix_ext_sess_org_status", "organisation_id", "status"),)


class ExtPageObservation(Base):
    __tablename__ = "ext_page_observations"
    observation_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    session_id = Column(String(64), nullable=True, index=True)
    url = Column(String(2048), nullable=False)
    title = Column(String(512), default="")
    content_hash = Column(String(128), nullable=True)
    observation = Column(JSON, default=dict)
    trust = Column(String(32), default="EXTERNAL_UNTRUSTED")
    created_at = Column(DateTime, default=datetime.utcnow)


class ExtAction(Base):
    __tablename__ = "ext_actions"
    action_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    session_id = Column(String(64), nullable=True)
    capability_id = Column(String(64), nullable=False)
    target = Column(String(2048), default="")
    content_hash = Column(String(128), nullable=True)
    idempotency_key = Column(String(128), nullable=True, index=True)
    status = Column(String(32), default="REQUESTED")
    decision = Column(String(64), default="")
    decision_reason = Column(String(128), default="")
    result = Column(JSON, default=dict)
    verification = Column(String(32), nullable=True)  # SUCCESS|FAILED|UNKNOWN
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class ExtApproval(Base):
    __tablename__ = "ext_approvals"
    approval_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    action_id = Column(String(64), nullable=True)
    capability_id = Column(String(64), default="")
    target = Column(String(2048), default="")
    content = Column(Text, default="")
    risk = Column(String(32), default="MEDIUM")
    status = Column(String(32), default="PENDING")
    reason = Column(Text, default="")
    decided_by = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    decided_at = Column(DateTime, nullable=True)


class ExtResearchSession(Base):
    __tablename__ = "ext_research_sessions"
    research_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    query = Column(Text, default="")
    status = Column(String(32), default="RUNNING")
    sources = Column(JSON, default=list)
    findings = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class ExtMediaJob(Base):
    __tablename__ = "ext_media_jobs"
    job_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    media_type = Column(String(32), default="video")
    source_url = Column(String(2048), default="")
    status = Column(String(32), default="PENDING")
    result = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class ExtAccount(Base):
    __tablename__ = "ext_accounts"
    account_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    platform = Column(String(64), nullable=False)
    display_name = Column(String(256), default="")
    credential_ref = Column(String(256), nullable=True)  # vault reference, never raw password
    status = Column(String(32), default="ACTIVE")
    permissions = Column(JSON, default=list)
    meta = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
