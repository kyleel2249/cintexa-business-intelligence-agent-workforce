"""Durable evolution / change-management schema."""

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


class EvoProposal(Base):
    __tablename__ = "evo_proposals"
    proposal_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    title = Column(String(512), nullable=False)
    description = Column(Text, default="")
    category = Column(String(64), nullable=False, index=True)
    risk_level = Column(String(32), nullable=False)
    source = Column(String(128), default="observation")
    detected_problem = Column(Text, default="")
    evidence = Column(JSON, default=dict)
    root_cause = Column(Text, default="")
    root_cause_status = Column(String(64), default="NEEDS_MORE_EVIDENCE")
    baseline = Column(JSON, default=dict)
    proposed_change = Column(JSON, default=dict)
    expected_effect = Column(Text, default="")
    affected_components = Column(JSON, default=list)
    evaluation_plan = Column(JSON, default=dict)
    rollback_plan = Column(JSON, default=dict)
    status = Column(String(32), default="PROPOSED", index=True)
    content_hash = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (Index("ix_evo_prop_org_status", "organisation_id", "status"),)


class EvoExperiment(Base):
    __tablename__ = "evo_experiments"
    experiment_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    proposal_id = Column(String(64), nullable=True, index=True)
    hypothesis = Column(Text, default="")
    baseline = Column(JSON, default=dict)
    candidate = Column(JSON, default=dict)
    success_criteria = Column(JSON, default=dict)
    failure_criteria = Column(JSON, default=dict)
    status = Column(String(32), default="PLANNED")
    results = Column(JSON, default=dict)
    conclusion = Column(String(64), nullable=True)  # IMPROVED|REGRESSED|INCONCLUSIVE|FAILED
    shadow = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class EvoApproval(Base):
    __tablename__ = "evo_approvals"
    approval_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    proposal_id = Column(String(64), nullable=False, index=True)
    proposal_hash = Column(String(128), nullable=True)
    approver = Column(String(128), nullable=False)
    role = Column(String(64), default="human")
    decision = Column(String(32), nullable=False)  # APPROVED|REJECTED|APPROVED_WITH_CONDITIONS|REVOKED|EXPIRED
    reason = Column(Text, default="")
    risk_level = Column(String(32), default="")
    conditions = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)


class EvoRelease(Base):
    __tablename__ = "evo_releases"
    release_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    proposal_id = Column(String(64), nullable=True)
    version = Column(String(64), nullable=False)
    components = Column(JSON, default=dict)
    status = Column(String(32), default="STAGED")  # STAGED|CANARY|DEPLOYED|PROMOTED|ROLLED_BACK
    canary_percent = Column(Integer, default=0)
    rollback_target = Column(String(64), nullable=True)
    evaluation_results = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EvoDrift(Base):
    __tablename__ = "evo_drift_signals"
    drift_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    kind = Column(String(64), nullable=False)  # quality|latency|failure|retrieval|model|knowledge
    metric = Column(String(128), default="")
    baseline_value = Column(Float, nullable=True)
    current_value = Column(Float, nullable=True)
    status = Column(String(32), default="DETECTED")
    details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class EvoFeedback(Base):
    __tablename__ = "evo_feedback"
    feedback_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    kind = Column(String(64), default="correction")  # positive|negative|correction|...
    content = Column(Text, default="")
    execution_id = Column(String(64), nullable=True)
    agent_key = Column(String(128), nullable=True)
    linked_proposal_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class EvoKnowledgeCandidate(Base):
    __tablename__ = "evo_knowledge_candidates"
    candidate_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    content = Column(Text, default="")
    provenance = Column(JSON, default=dict)
    trust = Column(String(32), default="UNVERIFIED")  # UNVERIFIED|SOURCE_VERIFIED|USER_CONFIRMED
    status = Column(String(32), default="CANDIDATE")  # CANDIDATE|PROMOTED|REJECTED
    created_at = Column(DateTime, default=datetime.utcnow)
