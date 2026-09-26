"""Repository implementations — organisation-scoped persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.errors import ConflictError, NotFoundError
from database.models import (
    AgentRun,
    AgentTask,
    ArtifactRecord,
    AuditLog,
    CheckpointRecord,
    ConversationRecord,
    DurableEvent,
    Membership,
    MemoryRecord,
    MissionRecord,
    Organisation,
    User,
    WorkflowRecord,
    WorkflowStepRecord,
)
from schemas.common import new_id


class OrganisationRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, organisation_id: str) -> Optional[Organisation]:
        return self.session.get(Organisation, organisation_id)

    def create(self, organisation_id: str, name: str, **kwargs) -> Organisation:
        org = Organisation(id=organisation_id, name=name, **kwargs)
        self.session.add(org)
        self.session.flush()
        return org

    def get_or_create(self, organisation_id: str, name: Optional[str] = None) -> Organisation:
        org = self.get(organisation_id)
        if org:
            return org
        return self.create(organisation_id, name or organisation_id)


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, user_id: str) -> Optional[User]:
        return self.session.get(User, user_id)

    def create(
        self,
        user_id: str,
        organisation_id: str,
        email: str,
        hashed_password: str = "!",
        role: str = "member",
    ) -> User:
        user = User(
            id=user_id,
            organisation_id=organisation_id,
            email=email,
            hashed_password=hashed_password,
            role=role,
        )
        self.session.add(user)
        self.session.flush()
        return user

    def ensure_membership(
        self, organisation_id: str, user_id: str, role: str = "member"
    ) -> Membership:
        m = (
            self.session.query(Membership)
            .filter_by(organisation_id=organisation_id, user_id=user_id)
            .one_or_none()
        )
        if m:
            return m
        m = Membership(
            id=new_id("MEMB-"),
            organisation_id=organisation_id,
            user_id=user_id,
            role=role,
        )
        self.session.add(m)
        self.session.flush()
        return m

    def is_member(self, organisation_id: str, user_id: str) -> bool:
        return (
            self.session.query(Membership)
            .filter_by(organisation_id=organisation_id, user_id=user_id, status="active")
            .count()
            > 0
        )


class TaskRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, task_id: str, organisation_id: str) -> Optional[AgentTask]:
        row = self.session.get(AgentTask, task_id)
        if row and row.organisation_id != organisation_id:
            return None
        return row

    def create(self, **fields) -> AgentTask:
        if "task_id" not in fields:
            fields["task_id"] = new_id("TASK-")
        if fields.get("idempotency_key"):
            existing = (
                self.session.query(AgentTask)
                .filter_by(
                    organisation_id=fields["organisation_id"],
                    # idempotency via context metadata if present
                )
                .filter(AgentTask.context["idempotency_key"].as_string() == fields["idempotency_key"])
                .first()
                if False
                else None
            )
        task = AgentTask(**{k: v for k, v in fields.items() if hasattr(AgentTask, k) or k in (
            "task_id", "organisation_id", "user_id", "request", "objective", "state",
            "priority", "plan", "results", "evidence_ids", "errors",
            "requires_human_approval", "approval_status", "context",
            "created_at", "updated_at", "completed_at",
        )})
        self.session.add(task)
        self.session.flush()
        return task

    def update(self, task_id: str, organisation_id: str, **fields) -> AgentTask:
        task = self.get(task_id, organisation_id)
        if not task:
            raise NotFoundError(f"Task {task_id} not found")
        for k, v in fields.items():
            if hasattr(task, k):
                setattr(task, k, v)
        task.updated_at = datetime.utcnow()
        self.session.flush()
        return task

    def list_for_org(
        self, organisation_id: str, *, state: Optional[str] = None, limit: int = 100
    ) -> List[AgentTask]:
        q = self.session.query(AgentTask).filter_by(organisation_id=organisation_id)
        if state:
            q = q.filter_by(state=state)
        return q.order_by(AgentTask.created_at.desc()).limit(limit).all()


class WorkflowRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, workflow_id: str, organisation_id: str) -> Optional[WorkflowRecord]:
        row = self.session.get(WorkflowRecord, workflow_id)
        if row and row.organisation_id != organisation_id:
            return None
        return row

    def get_by_idempotency(
        self, organisation_id: str, key: str
    ) -> Optional[WorkflowRecord]:
        return (
            self.session.query(WorkflowRecord)
            .filter_by(organisation_id=organisation_id, idempotency_key=key)
            .one_or_none()
        )

    def create(self, **fields) -> WorkflowRecord:
        if "workflow_id" not in fields:
            fields["workflow_id"] = new_id("WF-")
        # strip unknown
        allowed = {c.name for c in WorkflowRecord.__table__.columns}
        data = {k: v for k, v in fields.items() if k in allowed}
        if "metadata" in fields and "metadata_json" not in data:
            data["metadata_json"] = fields["metadata"]
        row = WorkflowRecord(**data)
        self.session.add(row)
        self.session.flush()
        return row

    def update(
        self, workflow_id: str, organisation_id: str, *, expected_version: Optional[int] = None, **fields
    ) -> WorkflowRecord:
        row = self.get(workflow_id, organisation_id)
        if not row:
            raise NotFoundError(f"Workflow {workflow_id} not found")
        if expected_version is not None and row.version != expected_version:
            raise ConflictError(
                f"Workflow version conflict: expected {expected_version}, got {row.version}"
            )
        for k, v in fields.items():
            if k == "metadata":
                row.metadata_json = v
            elif hasattr(row, k):
                setattr(row, k, v)
        row.version = (row.version or 1) + 1
        row.updated_at = datetime.utcnow()
        self.session.flush()
        return row

    def add_step(self, **fields) -> WorkflowStepRecord:
        if "step_id" not in fields:
            fields["step_id"] = new_id("STEP-")
        allowed = {c.name for c in WorkflowStepRecord.__table__.columns}
        data = {k: v for k, v in fields.items() if k in allowed}
        step = WorkflowStepRecord(**data)
        self.session.add(step)
        self.session.flush()
        return step

    def list_steps(self, workflow_id: str, organisation_id: str) -> List[WorkflowStepRecord]:
        return (
            self.session.query(WorkflowStepRecord)
            .filter_by(workflow_id=workflow_id, organisation_id=organisation_id)
            .order_by(WorkflowStepRecord.sequence)
            .all()
        )


class MissionRepository:
    """Persist full mission payloads (orchestrator)."""

    def __init__(self, session: Session):
        self.session = session

    def get(self, mission_id: str, organisation_id: str) -> Optional[MissionRecord]:
        row = self.session.get(MissionRecord, mission_id)
        if row and row.organisation_id != organisation_id:
            return None
        return row

    def get_by_idempotency(self, organisation_id: str, key: str) -> Optional[MissionRecord]:
        return (
            self.session.query(MissionRecord)
            .filter_by(organisation_id=organisation_id, idempotency_key=key)
            .one_or_none()
        )

    def save_payload(self, mission_dict: Dict[str, Any]) -> MissionRecord:
        mid = mission_dict["mission_id"]
        org = mission_dict.get("organisation_id", "default-org")
        row = self.session.get(MissionRecord, mid)
        if not row:
            row = MissionRecord(mission_id=mid, organisation_id=org, user_id=mission_dict.get("user_id", "default-user"))
            self.session.add(row)
        row.organisation_id = org
        row.workspace_id = mission_dict.get("workspace_id", "default-workspace")
        row.user_id = mission_dict.get("user_id", "default-user")
        row.objective = mission_dict.get("objective") or ""
        row.original_request = mission_dict.get("original_request") or ""
        row.status = mission_dict.get("status") or "CREATED"
        if hasattr(row.status, "value"):
            row.status = row.status.value
        if isinstance(mission_dict.get("status"), str):
            row.status = mission_dict["status"]
        elif mission_dict.get("status") is not None and hasattr(mission_dict["status"], "value"):
            row.status = mission_dict["status"].value
        row.priority = str(mission_dict.get("priority") or "NORMAL")
        if hasattr(mission_dict.get("priority"), "value"):
            row.priority = mission_dict["priority"].value
        row.business_domain = mission_dict.get("business_domain") or "general"
        row.plan_version = int(mission_dict.get("plan_version") or 0)
        row.confidence = float(mission_dict.get("confidence") or 0.0)
        row.quality_score = float(mission_dict.get("quality_score") or 0.0)
        row.idempotency_key = mission_dict.get("idempotency_key")
        row.payload = mission_dict
        self.session.flush()
        return row

    def list_for_org(self, organisation_id: str, limit: int = 50) -> List[MissionRecord]:
        return (
            self.session.query(MissionRecord)
            .filter_by(organisation_id=organisation_id)
            .order_by(MissionRecord.created_at.desc())
            .limit(limit)
            .all()
        )


class EventRepository:
    def __init__(self, session: Session):
        self.session = session

    def publish(
        self,
        *,
        organisation_id: str,
        event_type: str,
        payload: Optional[Dict] = None,
        aggregate_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        task_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> DurableEvent:
        ev = DurableEvent(
            event_id=event_id or new_id("EVT-"),
            organisation_id=organisation_id,
            event_type=event_type,
            aggregate_id=aggregate_id,
            workflow_id=workflow_id,
            task_id=task_id,
            payload=payload or {},
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
        self.session.add(ev)
        self.session.flush()
        return ev

    def list_for_org(
        self,
        organisation_id: str,
        *,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[DurableEvent]:
        q = self.session.query(DurableEvent).filter_by(organisation_id=organisation_id)
        if event_type:
            q = q.filter_by(event_type=event_type)
        return q.order_by(DurableEvent.created_at.desc()).limit(limit).all()


class MemoryRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        organisation_id: str,
        content: Any,
        memory_type: str = "working",
        user_id: Optional[str] = None,
        source: str = "agent",
        task_id: Optional[str] = None,
        mission_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> MemoryRecord:
        row = MemoryRecord(
            memory_id=new_id("MEM-"),
            organisation_id=organisation_id,
            user_id=user_id,
            memory_type=memory_type,
            content=content if isinstance(content, dict) else {"text": content},
            source=source,
            task_id=task_id,
            mission_id=mission_id,
            metadata_json=metadata or {},
        )
        self.session.add(row)
        self.session.flush()
        return row

    def get(self, memory_id: str, organisation_id: str) -> Optional[MemoryRecord]:
        row = self.session.get(MemoryRecord, memory_id)
        if row and row.organisation_id != organisation_id:
            return None
        return row

    def list_for_org(
        self,
        organisation_id: str,
        *,
        memory_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[MemoryRecord]:
        q = self.session.query(MemoryRecord).filter_by(organisation_id=organisation_id, status="active")
        if memory_type:
            q = q.filter_by(memory_type=memory_type)
        return q.order_by(MemoryRecord.created_at.desc()).limit(limit).all()

    def search(
        self, organisation_id: str, query: str, *, memory_type: Optional[str] = None, limit: int = 50
    ) -> List[MemoryRecord]:
        items = self.list_for_org(organisation_id, memory_type=memory_type, limit=500)
        q = query.lower()
        return [i for i in items if q in str(i.content).lower()][:limit]

    def delete(self, memory_id: str, organisation_id: str) -> bool:
        row = self.get(memory_id, organisation_id)
        if not row:
            return False
        row.status = "deleted"
        self.session.flush()
        return True


class CheckpointRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        workflow_id: str,
        organisation_id: str,
        current_step: Optional[str] = None,
        completed_steps: Optional[List] = None,
        pending_steps: Optional[List] = None,
        state_refs: Optional[Dict] = None,
        execution_metadata: Optional[Dict] = None,
        version: int = 1,
    ) -> CheckpointRecord:
        row = CheckpointRecord(
            checkpoint_id=new_id("CP-"),
            workflow_id=workflow_id,
            organisation_id=organisation_id,
            current_step=current_step,
            completed_steps=completed_steps or [],
            pending_steps=pending_steps or [],
            state_refs=state_refs or {},
            execution_metadata=execution_metadata or {},
            version=version,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def latest(self, workflow_id: str, organisation_id: str) -> Optional[CheckpointRecord]:
        return (
            self.session.query(CheckpointRecord)
            .filter_by(workflow_id=workflow_id, organisation_id=organisation_id)
            .order_by(CheckpointRecord.version.desc())
            .first()
        )


class ConversationRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, session_id: str, organisation_id: str) -> Optional[ConversationRecord]:
        row = self.session.get(ConversationRecord, session_id)
        if row and row.organisation_id != organisation_id:
            return None
        return row

    def save(
        self,
        *,
        session_id: str,
        organisation_id: str,
        user_id: str,
        title: str = "New chat",
        messages: Optional[List] = None,
        mission_id: Optional[str] = None,
    ) -> ConversationRecord:
        row = self.session.get(ConversationRecord, session_id)
        if not row:
            row = ConversationRecord(
                session_id=session_id,
                organisation_id=organisation_id,
                user_id=user_id,
            )
            self.session.add(row)
        if row.organisation_id != organisation_id:
            raise NotFoundError("Conversation not found for organisation")
        row.title = title
        row.messages = messages or row.messages or []
        row.mission_id = mission_id
        row.updated_at = datetime.utcnow()
        self.session.flush()
        return row

    def list_for_user(self, organisation_id: str, user_id: str, limit: int = 50) -> List[ConversationRecord]:
        return (
            self.session.query(ConversationRecord)
            .filter_by(organisation_id=organisation_id, user_id=user_id)
            .order_by(ConversationRecord.updated_at.desc())
            .limit(limit)
            .all()
        )


class AuditRepository:
    def __init__(self, session: Session):
        self.session = session

    def record(
        self,
        *,
        organisation_id: str,
        actor: str,
        action: str,
        resource_type: str,
        resource_id: str,
        details: Optional[Dict] = None,
    ) -> AuditLog:
        row = AuditLog(
            log_id=new_id("AUD-"),
            organisation_id=organisation_id,
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
        )
        self.session.add(row)
        self.session.flush()
        return row
