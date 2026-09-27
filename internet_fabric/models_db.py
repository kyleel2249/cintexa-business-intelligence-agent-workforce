"""Durable internet research models — integrate with Phase 1 persistence."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    JSON,
    String,
    Text,
)

from database.models import Base


class InternetResearchCase(Base):
    __tablename__ = "inet_research_cases"
    research_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    agent_id = Column(String(64), nullable=True)
    question = Column(Text, nullable=False)
    depth = Column(String(32), default="STANDARD")  # SURFACE|STANDARD|DEEP|EXHAUSTIVE
    status = Column(String(32), default="PLANNING")  # PLANNING|SEARCHING|RETRIEVING|SYNTHESIZING|COMPLETED|FAILED
    methodology = Column(JSON, default=dict)
    findings = Column(JSON, default=list)
    limitations = Column(JSON, default=list)
    unanswered = Column(JSON, default=list)
    budget = Column(JSON, default=dict)
    budget_used = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (Index("ix_inet_case_org_status", "organisation_id", "status"),)


class InternetSource(Base):
    __tablename__ = "inet_sources"
    source_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    research_id = Column(String(64), nullable=True, index=True)
    url = Column(String(2048), nullable=False)
    domain = Column(String(256), nullable=True, index=True)
    title = Column(String(512), default="")
    publisher = Column(String(256), default="")
    content_type = Column(String(64), default="html")
    source_category = Column(String(64), default="UNKNOWN")
    reliability = Column(String(32), default="UNKNOWN")
    content_hash = Column(String(128), nullable=True)
    retrieved_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    access_status = Column(String(32), default="OK")  # OK|ACCESS_FAILED|ACCESS_RESTRICTED|BLOCKED_BY_POLICY
    meta = Column(JSON, default=dict)
    trust = Column(String(32), default="UNTRUSTED_EXTERNAL_CONTENT")
    created_at = Column(DateTime, default=datetime.utcnow)


class InternetEvidence(Base):
    __tablename__ = "inet_evidence"
    evidence_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    research_id = Column(String(64), nullable=True, index=True)
    source_id = Column(String(64), nullable=True, index=True)
    source_url = Column(String(2048), default="")
    source_location = Column(String(256), default="")  # page, section, timestamp
    extracted_text = Column(Text, default="")
    structured_value = Column(JSON, default=dict)
    extraction_method = Column(String(64), default="text")
    confidence = Column(String(32), default="unverified")
    agent_id = Column(String(64), nullable=True)
    trust = Column(String(32), default="UNTRUSTED_EXTERNAL_CONTENT")
    created_at = Column(DateTime, default=datetime.utcnow)


class InternetClaim(Base):
    __tablename__ = "inet_claims"
    claim_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    research_id = Column(String(64), nullable=True, index=True)
    statement = Column(Text, nullable=False)
    status = Column(String(32), default="UNKNOWN")  # VERIFIED|SUPPORTED|PARTIALLY_SUPPORTED|CONTESTED|UNSUPPORTED|CONTRADICTED|UNKNOWN
    supporting_evidence_ids = Column(JSON, default=list)
    contradicting_evidence_ids = Column(JSON, default=list)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class InternetConflict(Base):
    __tablename__ = "inet_conflicts"
    conflict_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    research_id = Column(String(64), nullable=True, index=True)
    claim = Column(Text, default="")
    source_a_id = Column(String(64), nullable=True)
    source_b_id = Column(String(64), nullable=True)
    details = Column(JSON, default=dict)
    resolution_status = Column(String(32), default="OPEN")
    created_at = Column(DateTime, default=datetime.utcnow)


class InternetSearchLog(Base):
    __tablename__ = "inet_search_logs"
    log_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    research_id = Column(String(64), nullable=True, index=True)
    provider = Column(String(64), default="")
    query = Column(Text, default="")
    status = Column(String(32), default="OK")
    latency_ms = Column(Float, default=0.0)
    result_count = Column(Integer, default=0)
    failure = Column(Text, default="")
    fallback_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ExternalAPIConnector(Base):
    __tablename__ = "inet_api_connectors"
    connector_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    base_url = Column(String(2048), nullable=False)
    auth_type = Column(String(32), default="none")  # none|api_key|oauth|bearer
    credential_ref = Column(String(256), nullable=True)  # vault ref, never raw secret
    endpoints = Column(JSON, default=list)
    rate_limit = Column(JSON, default=dict)
    enabled = Column(Boolean, default=True)
    meta = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
