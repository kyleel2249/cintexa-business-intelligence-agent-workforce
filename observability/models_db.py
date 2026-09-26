"""Durable observability & evaluation schema."""

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


class ObsSpan(Base):
    __tablename__ = "obs_spans"
    span_id = Column(String(64), primary_key=True)
    trace_id = Column(String(64), nullable=False, index=True)
    parent_span_id = Column(String(64), nullable=True)
    organisation_id = Column(String(64), nullable=True, index=True)
    correlation_id = Column(String(64), nullable=True, index=True)
    workflow_id = Column(String(64), nullable=True)
    task_id = Column(String(64), nullable=True)
    agent_id = Column(String(64), nullable=True)
    operation = Column(String(256), nullable=False)
    component = Column(String(128), default="app")
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=True)
    duration_ms = Column(Float, nullable=True)
    status = Column(String(32), default="RUNNING")
    attributes = Column(JSON, default=dict)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_obs_span_org_time", "organisation_id", "start_time"),)


class ObsLog(Base):
    __tablename__ = "obs_logs"
    log_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=True, index=True)
    correlation_id = Column(String(64), nullable=True, index=True)
    trace_id = Column(String(64), nullable=True)
    severity = Column(String(16), default="INFO")
    component = Column(String(128), default="app")
    message = Column(Text, default="")
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (Index("ix_obs_log_org_time", "organisation_id", "created_at"),)


class ObsMetricSnapshot(Base):
    __tablename__ = "obs_metric_snapshots"
    snapshot_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=True, index=True)
    name = Column(String(256), nullable=False)
    kind = Column(String(32), default="counter")  # counter|histogram
    value_json = Column(JSON, default=dict)
    captured_at = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class EvalDataset(Base):
    __tablename__ = "eval_datasets"
    dataset_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    name = Column(String(256), nullable=False)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class EvalDatasetVersion(Base):
    __tablename__ = "eval_dataset_versions"
    version_id = Column(String(64), primary_key=True)
    dataset_id = Column(String(64), nullable=False, index=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    version = Column(String(64), nullable=False)
    immutable = Column(Boolean, default=True)
    cases = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("dataset_id", "version", name="uq_eval_ds_ver"),)


class EvalRun(Base):
    __tablename__ = "eval_runs"
    run_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    dataset_version_id = Column(String(64), nullable=True)
    system_version = Column(String(64), default="1.0.0")
    status = Column(String(32), default="RUNNING")
    cases_total = Column(Integer, default=0)
    cases_passed = Column(Integer, default=0)
    cases_failed = Column(Integer, default=0)
    cases_unknown = Column(Integer, default=0)
    metrics = Column(JSON, default=dict)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class EvalResult(Base):
    __tablename__ = "eval_results"
    result_id = Column(String(64), primary_key=True)
    run_id = Column(String(64), nullable=False, index=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    case_id = Column(String(64), nullable=True)
    status = Column(String(32), default="UNKNOWN")  # PASS|FAIL|UNKNOWN|NEEDS_HUMAN_REVIEW
    dimensions = Column(JSON, default=dict)
    expected = Column(JSON, default=dict)
    actual = Column(JSON, default=dict)
    evidence = Column(JSON, default=dict)
    method = Column(String(64), default="deterministic")
    created_at = Column(DateTime, default=datetime.utcnow)


class ObsReplay(Base):
    __tablename__ = "obs_replays"
    replay_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    source_execution_id = Column(String(64), nullable=True)
    source_trace_id = Column(String(64), nullable=True)
    mode = Column(String(32), default="READ_ONLY_REPLAY")
    status = Column(String(32), default="CREATED")
    payload = Column(JSON, default=dict)
    result = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class ObsAlert(Base):
    __tablename__ = "obs_alerts"
    alert_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    rule = Column(String(128), nullable=False)
    severity = Column(String(16), default="WARNING")
    message = Column(Text, default="")
    value = Column(Float, nullable=True)
    threshold = Column(Float, nullable=True)
    status = Column(String(32), default="OPEN")
    related_trace_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ObsIncident(Base):
    __tablename__ = "obs_incidents"
    incident_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    severity = Column(String(16), default="MEDIUM")
    title = Column(String(512), default="")
    status = Column(String(32), default="OPEN")
    symptoms = Column(Text, default="")
    related = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


class ObsDefect(Base):
    __tablename__ = "obs_defects"
    defect_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    category = Column(String(64), default="quality")
    severity = Column(String(16), default="MEDIUM")
    description = Column(Text, default="")
    expected = Column(Text, default="")
    actual = Column(Text, default="")
    evidence = Column(JSON, default=dict)
    status = Column(String(32), default="OPEN")
    regression_case_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ObsQualityProfile(Base):
    __tablename__ = "obs_quality_profiles"
    profile_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    subject_type = Column(String(32), nullable=False)  # agent|model|workflow
    subject_key = Column(String(128), nullable=False)
    version = Column(String(64), default="1.0.0")
    metrics = Column(JSON, default=dict)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (Index("ix_obs_qp_org_subj", "organisation_id", "subject_type", "subject_key"),)
