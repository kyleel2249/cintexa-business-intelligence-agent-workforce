"""Shared enums and base models for CINTEXA BI."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def new_id(prefix: str = "") -> str:
    uid = str(uuid4())
    return f"{prefix}{uid}" if prefix else uid


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class ConfidenceReason(str, Enum):
    MEASURED = "MEASURED"
    ESTIMATED = "ESTIMATED"
    INFERRED = "INFERRED"
    USER_PROVIDED = "USER_PROVIDED"
    EXTERNALLY_REPORTED = "EXTERNALLY_REPORTED"
    MODEL_GENERATED = "MODEL_GENERATED"


class Classification(str, Enum):
    CONFIRMED = "CONFIRMED"
    PUBLICLY_REPORTED = "PUBLICLY_REPORTED"
    ESTIMATED = "ESTIMATED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class SourceQuality(str, Enum):
    A = "A"  # primary / high authority
    B = "B"  # reputable secondary
    C = "C"  # useful but limited
    D = "D"  # weak / unverified


class TaskState(str, Enum):
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    WAITING_FOR_DATA = "WAITING_FOR_DATA"
    WAITING_FOR_AGENT = "WAITING_FOR_AGENT"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"


class MessageType(str, Enum):
    REQUEST = "request"
    RESPONSE = "response"
    HANDOFF = "handoff"
    CLARIFICATION = "clarification"
    WARNING = "warning"
    FAILURE = "failure"
    APPROVAL_REQUEST = "approval_request"
    COMPLETION = "completion"
    RESEARCH_RESULT = "research_result"


class QAResult(str, Enum):
    APPROVED = "APPROVED"
    REVISION_REQUIRED = "REVISION_REQUIRED"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TimestampedModel(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class ConfidenceInfo(BaseModel):
    level: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    reason: ConfidenceReason = ConfidenceReason.MODEL_GENERATED
    score: Optional[float] = Field(None, ge=0.0, le=1.0)
    notes: Optional[str] = None


class EvidenceRef(BaseModel):
    evidence_id: str
    claim: Optional[str] = None
    supports: List[str] = Field(default_factory=list)
