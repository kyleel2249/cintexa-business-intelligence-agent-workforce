"""Mission-level schemas for CINTEXA Workforce Orchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from schemas.common import Priority, new_id


class MissionStatus(str, Enum):
    CREATED = "CREATED"
    UNDERSTANDING = "UNDERSTANDING"
    PLANNING = "PLANNING"
    WAITING_FOR_INPUT = "WAITING_FOR_INPUT"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    BLOCKED = "BLOCKED"
    REPLANNING = "REPLANNING"
    VERIFYING = "VERIFYING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AmbiguityLevel(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EvidenceSufficiency(str, Enum):
    INSUFFICIENT = "INSUFFICIENT"
    LIMITED = "LIMITED"
    ADEQUATE = "ADEQUATE"
    STRONG = "STRONG"
    VERY_STRONG = "VERY_STRONG"


class HypothesisStatus(str, Enum):
    PROPOSED = "PROPOSED"
    TESTING = "TESTING"
    SUPPORTED = "SUPPORTED"
    WEAKENED = "WEAKENED"
    REJECTED = "REJECTED"
    UNRESOLVED = "UNRESOLVED"


class ConflictResolution(str, Enum):
    CLAIM_A_SUPPORTED = "CLAIM_A_SUPPORTED"
    CLAIM_B_SUPPORTED = "CLAIM_B_SUPPORTED"
    BOTH_PARTIALLY_SUPPORTED = "BOTH_PARTIALLY_SUPPORTED"
    DEFINITION_CONFLICT = "DEFINITION_CONFLICT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNRESOLVED = "UNRESOLVED"


class FailureClass(str, Enum):
    TIMEOUT = "TIMEOUT"
    TOOL_FAILURE = "TOOL_FAILURE"
    MODEL_FAILURE = "MODEL_FAILURE"
    DATA_FAILURE = "DATA_FAILURE"
    PERMISSION_FAILURE = "PERMISSION_FAILURE"
    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    RESOURCE_FAILURE = "RESOURCE_FAILURE"
    LOGIC_FAILURE = "LOGIC_FAILURE"
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"


class MissionPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"
    CRITICAL = "CRITICAL"


class Assumption(BaseModel):
    assumption: str
    reason: str = ""
    impact: str = "medium"
    requires_confirmation: bool = False


class IntentModel(BaseModel):
    goal: str = ""
    desired_outcome: str = ""
    business_domain: str = "general"
    requested_actions: List[str] = Field(default_factory=list)
    requested_analysis: List[str] = Field(default_factory=list)
    requested_deliverables: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    time_horizon: Optional[str] = None
    geography: Optional[str] = None
    audience: Optional[str] = None
    priority: MissionPriority = MissionPriority.NORMAL
    urgency: str = "normal"
    risk: str = "medium"
    required_accuracy: str = "medium"
    required_sources: List[str] = Field(default_factory=list)
    known_data: List[str] = Field(default_factory=list)
    missing_data: List[str] = Field(default_factory=list)
    implicit_tasks: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    approval_requirements: List[str] = Field(default_factory=list)
    ambiguity: AmbiguityLevel = AmbiguityLevel.LOW
    assumptions: List[Assumption] = Field(default_factory=list)
    raw_confidence: float = 0.7


class NormalizedObjective(BaseModel):
    objective: str
    desired_outcome: str = ""
    time_horizon: Optional[str] = None
    analysis_requirements: List[str] = Field(default_factory=list)
    deliverables: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    success_criteria: List[str] = Field(default_factory=list)


class MissionTaskStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


class MissionTask(BaseModel):
    task_id: str = Field(default_factory=lambda: new_id("MTASK-"))
    objective: str
    required_skills: List[str] = Field(default_factory=list)
    required_tools: List[str] = Field(default_factory=list)
    required_capabilities: List[str] = Field(default_factory=list)
    required_permissions: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    evidence_requirements: List[str] = Field(default_factory=list)
    priority: float = 0.5
    risk_level: str = "medium"
    timeout_seconds: int = 120
    max_attempts: int = 2
    success_criteria: List[str] = Field(default_factory=list)
    assigned_agent_id: Optional[str] = None
    role: Optional[str] = None
    status: MissionTaskStatus = MissionTaskStatus.PENDING
    result: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    evidence_ids: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    attempts: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class MissionPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: new_id("PLAN-"))
    version: int = 1
    tasks: List[MissionTask] = Field(default_factory=list)
    parallel_groups: List[List[str]] = Field(default_factory=list)
    sequential_tail: List[str] = Field(default_factory=list)
    team: List[str] = Field(default_factory=list)
    rationale: str = ""
    change_reason: Optional[str] = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat() + "Z"
    )


class Hypothesis(BaseModel):
    hypothesis_id: str = Field(default_factory=lambda: new_id("HYP-"))
    statement: str
    supporting_evidence: List[str] = Field(default_factory=list)
    contradicting_evidence: List[str] = Field(default_factory=list)
    confidence: float = 0.5
    required_tests: List[str] = Field(default_factory=list)
    status: HypothesisStatus = HypothesisStatus.PROPOSED


class Conflict(BaseModel):
    conflict_id: str = Field(default_factory=lambda: new_id("CONF-"))
    claims: List[str] = Field(default_factory=list)
    agents: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    severity: str = "medium"
    affected_tasks: List[str] = Field(default_factory=list)
    resolution_status: ConflictResolution = ConflictResolution.UNRESOLVED
    resolution_notes: str = ""


class OrchestrationDecision(BaseModel):
    decision_id: str = Field(default_factory=lambda: new_id("ODEC-"))
    mission_id: str
    decision_type: str
    decision: str
    reason: str = ""
    available_options: List[str] = Field(default_factory=list)
    selected_option: str = ""
    supporting_evidence: List[str] = Field(default_factory=list)
    confidence: float = 0.7
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat() + "Z"
    )
    agent_or_system: str = "orchestrator"


class MissionCreate(BaseModel):
    objective: str
    organisation_id: str = "default-org"
    workspace_id: str = "default-workspace"
    user_id: str = "default-user"
    priority: MissionPriority = MissionPriority.NORMAL
    context: Dict[str, Any] = Field(default_factory=dict)
    constraints: List[str] = Field(default_factory=list)
    deadline: Optional[str] = None
    success_criteria: List[str] = Field(default_factory=list)
    required_outputs: List[str] = Field(default_factory=list)
    approval_requirements: List[str] = Field(default_factory=list)
    idempotency_key: Optional[str] = None


class MissionResult(BaseModel):
    mission_id: str
    status: MissionStatus
    objective: str
    summary: str = ""
    findings: List[Any] = Field(default_factory=list)
    evidence: List[Any] = Field(default_factory=list)
    assumptions: List[Assumption] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)
    conflicts: List[Conflict] = Field(default_factory=list)
    decisions: List[OrchestrationDecision] = Field(default_factory=list)
    actions: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    quality: float = 0.0
    limitations: List[str] = Field(default_factory=list)
    execution_trace: str = ""
    deliverables: Dict[str, Any] = Field(default_factory=dict)


class Mission(BaseModel):
    mission_id: str = Field(default_factory=lambda: new_id("MISSION-"))
    organisation_id: str = "default-org"
    workspace_id: str = "default-workspace"
    user_id: str = "default-user"
    objective: str = ""
    original_request: str = ""
    normalized_objective: Optional[NormalizedObjective] = None
    intent: Optional[IntentModel] = None
    priority: MissionPriority = MissionPriority.NORMAL
    urgency: str = "normal"
    risk_level: str = "medium"
    business_domain: str = "general"
    constraints: List[str] = Field(default_factory=list)
    success_criteria: List[str] = Field(default_factory=list)
    required_outputs: List[str] = Field(default_factory=list)
    available_context: Dict[str, Any] = Field(default_factory=dict)
    missing_information: List[str] = Field(default_factory=list)
    plan: Optional[MissionPlan] = None
    plan_history: List[MissionPlan] = Field(default_factory=list)
    plan_version: int = 0
    status: MissionStatus = MissionStatus.CREATED
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat() + "Z"
    )
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    deadline: Optional[str] = None
    approval_requirements: List[str] = Field(default_factory=list)
    assigned_agents: List[str] = Field(default_factory=list)
    tasks: List[MissionTask] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    decisions: List[OrchestrationDecision] = Field(default_factory=list)
    actions: List[str] = Field(default_factory=list)
    hypotheses: List[Hypothesis] = Field(default_factory=list)
    conflicts: List[Conflict] = Field(default_factory=list)
    events: List[Dict[str, Any]] = Field(default_factory=list)
    quality_score: float = 0.0
    confidence: float = 0.0
    cost_metadata: Dict[str, Any] = Field(default_factory=dict)
    execution_metrics: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[MissionResult] = None
    idempotency_key: Optional[str] = None
    chat_session_id: Optional[str] = None
    errors: List[str] = Field(default_factory=list)
