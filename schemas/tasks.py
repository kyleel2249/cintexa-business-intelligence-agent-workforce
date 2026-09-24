"""Task planning, state and orchestration schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from schemas.common import Priority, TaskState, new_id


class TaskPlan(BaseModel):
    request: str
    objective: str
    agents_required: List[str] = Field(default_factory=list)
    priority: Priority = Priority.MEDIUM
    requires_web_research: bool = False
    requires_user_data: bool = False
    requires_human_approval: bool = False
    sequential_steps: List[str] = Field(default_factory=list)
    parallel_groups: List[List[str]] = Field(default_factory=list)
    dependencies: Dict[str, List[str]] = Field(default_factory=dict)
    estimated_tools: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)


class TaskCreate(BaseModel):
    request: str
    organisation_id: str
    user_id: str
    priority: Priority = Priority.MEDIUM
    context: Dict[str, Any] = Field(default_factory=dict)
    business_profile_id: Optional[str] = None
    attachments: List[str] = Field(default_factory=list)


class Task(BaseModel):
    task_id: str = Field(default_factory=lambda: new_id("TASK-"))
    request: str
    objective: Optional[str] = None
    organisation_id: str
    user_id: str
    priority: Priority = Priority.MEDIUM
    state: TaskState = TaskState.PENDING
    plan: Optional[TaskPlan] = None
    agents_assigned: List[str] = Field(default_factory=list)
    current_agent: Optional[str] = None
    results: Dict[str, Any] = Field(default_factory=dict)
    evidence_ids: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    requires_human_approval: bool = False
    approval_status: Optional[str] = None  # pending / granted / rejected
    context: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    parent_task_id: Optional[str] = None
    child_task_ids: List[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class TaskUpdate(BaseModel):
    state: Optional[TaskState] = None
    results: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None
    approval_status: Optional[str] = None


class ApprovalRequest(BaseModel):
    action: str
    reason: str
    data_used: Dict[str, Any] = Field(default_factory=dict)
    expected_effect: str
    risk: str
    approval_required: bool = True
    task_id: str
    requested_by: str
