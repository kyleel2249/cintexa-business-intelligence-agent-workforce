"""Phase 2 Agent OS durable tables (extend database.models Base)."""

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


class RegisteredAgent(Base):
    """Durable agent registry entry (per organisation or system-wide)."""

    __tablename__ = "aos_agents"
    id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)  # system = "__system__"
    agent_key = Column(String(128), nullable=False, index=True)  # logical id e.g. research
    name = Column(String(255), nullable=False)
    version = Column(String(32), nullable=False, default="1.0.0")
    is_active_version = Column(Boolean, default=True)
    lifecycle_state = Column(String(32), default="REGISTERED", index=True)
    capabilities = Column(JSON, default=list)  # list of capability names
    profile = Column(JSON, default=dict)
    health_score = Column(Float, default=1.0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    in_flight = Column(Integer, default=0)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("organisation_id", "agent_key", "version", name="uq_aos_agent_ver"),
        Index("ix_aos_agents_org_key", "organisation_id", "agent_key"),
        Index("ix_aos_agents_org_state", "organisation_id", "lifecycle_state"),
    )


class AgentCapabilityIndex(Base):
    """Inverted index: capability → agent for discovery."""

    __tablename__ = "aos_capabilities"
    id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    capability = Column(String(128), nullable=False, index=True)
    agent_id = Column(String(64), nullable=False, index=True)  # RegisteredAgent.id
    agent_key = Column(String(128), nullable=False)
    version = Column(String(32), nullable=False)
    enabled = Column(Boolean, default=True)

    __table_args__ = (
        Index("ix_aos_cap_org_cap", "organisation_id", "capability"),
        UniqueConstraint("organisation_id", "capability", "agent_id", name="uq_aos_cap_agent"),
    )


class AgentExecutionRecord(Base):
    """Every meaningful agent execution."""

    __tablename__ = "aos_executions"
    execution_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    agent_id = Column(String(64), nullable=False, index=True)
    agent_key = Column(String(128), nullable=False)
    agent_version = Column(String(32), nullable=False)
    task_id = Column(String(64), nullable=True, index=True)
    workflow_id = Column(String(64), nullable=True, index=True)
    status = Column(String(32), default="PENDING", index=True)
    input_ref = Column(JSON, default=dict)
    output_ref = Column(JSON, default=dict)
    error = Column(Text, nullable=True)
    correlation_id = Column(String(64), nullable=True, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_aos_exec_org_agent", "organisation_id", "agent_key"),
    )


class AgentMessageRecordOS(Base):
    """Structured inter-agent communication."""

    __tablename__ = "aos_messages"
    message_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    message_type = Column(String(32), nullable=False)  # REQUEST|RESPONSE|HANDOFF|ERROR|ESCALATION|CLARIFICATION
    sender = Column(String(128), nullable=False)
    recipient = Column(String(128), nullable=False)
    task_id = Column(String(64), nullable=True, index=True)
    workflow_id = Column(String(64), nullable=True, index=True)
    correlation_id = Column(String(64), nullable=True, index=True)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class EscalationRecord(Base):
    __tablename__ = "aos_escalations"
    escalation_id = Column(String(64), primary_key=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    task_id = Column(String(64), nullable=True, index=True)
    workflow_id = Column(String(64), nullable=True, index=True)
    agent_key = Column(String(128), nullable=True)
    reason = Column(Text, default="")
    status = Column(String(32), default="OPEN")  # OPEN|RESOLVED|CANCELLED
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


class WorkflowGraphNode(Base):
    """DAG node for Agent OS workflow graphs."""

    __tablename__ = "aos_graph_nodes"
    node_id = Column(String(64), primary_key=True)
    workflow_id = Column(String(64), nullable=False, index=True)
    organisation_id = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    agent_key = Column(String(128), nullable=True)
    capability = Column(String(128), nullable=True)
    status = Column(String(32), default="PENDING")
    depends_on = Column(JSON, default=list)  # list of node_ids
    input_data = Column(JSON, default=dict)
    output_data = Column(JSON, default=dict)
    assigned_agent_id = Column(String(64), nullable=True)
    sequence = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_aos_graph_wf", "workflow_id", "organisation_id"),
    )
