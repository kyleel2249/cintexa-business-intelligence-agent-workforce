"""Agent identity, capabilities, permissions and message protocol."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from schemas.common import (
    ConfidenceInfo,
    MessageType,
    Priority,
    TaskState,
    new_id,
)


class AgentCapability(BaseModel):
    name: str
    description: str
    tools_required: List[str] = Field(default_factory=list)


class AgentToolPermission(BaseModel):
    tool_name: str
    allowed: bool = True
    conditional: bool = False
    requires_approval: bool = False
    notes: Optional[str] = None


class AgentProfile(BaseModel):
    agent_id: str
    name: str
    role: str
    description: str
    capabilities: List[AgentCapability] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    permissions: List[AgentToolPermission] = Field(default_factory=list)
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    confidence_rules: List[str] = Field(default_factory=list)
    escalation_rules: List[str] = Field(default_factory=list)
    validation_rules: List[str] = Field(default_factory=list)
    memory_rules: List[str] = Field(default_factory=list)
    audit_requirements: List[str] = Field(default_factory=list)
    enabled: bool = True
    version: str = "1.0.0"


class AgentMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: new_id("MSG-"))
    task_id: str
    from_agent: str
    to_agent: str
    message_type: MessageType
    priority: Priority = Priority.MEDIUM
    data: Dict[str, Any] = Field(default_factory=dict)
    evidence_ids: List[str] = Field(default_factory=list)
    confidence: Optional[ConfidenceInfo] = None
    requires_response: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentRunRecord(BaseModel):
    run_id: str = Field(default_factory=lambda: new_id("RUN-"))
    agent_id: str
    task_id: str
    status: TaskState = TaskState.PENDING
    input_summary: Optional[str] = None
    tools_used: List[str] = Field(default_factory=list)
    output_summary: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    retries: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    qa_result: Optional[str] = None


class AgentActivityLog(BaseModel):
    log_id: str = Field(default_factory=lambda: new_id("LOG-"))
    agent: str
    task: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    input: Optional[Dict[str, Any]] = None
    tools_used: List[str] = Field(default_factory=list)
    output: Optional[Dict[str, Any]] = None
    evidence: List[str] = Field(default_factory=list)
    status: TaskState
    errors: List[str] = Field(default_factory=list)
    retries: int = 0
    qa_result: Optional[str] = None
    organisation_id: Optional[str] = None
