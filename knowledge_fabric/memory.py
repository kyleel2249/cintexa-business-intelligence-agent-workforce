"""Standardized multi-type memory service — shared Knowledge Fabric memory."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.errors import NotFoundError
from events.bus import bus
from knowledge_fabric.models_db import KFMemory
from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id


class MemoryService:
    def store(
        self,
        *,
        organisation_id: str,
        memory_type: str,
        content: Any,
        user_id: Optional[str] = None,
        agent_key: Optional[str] = None,
        task_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        trust_level: str = "AGENT_DERIVED",
        provenance: Optional[Dict] = None,
        scope: str = "org",
    ) -> Dict[str, Any]:
        mid = new_id("KFM-")
        payload = content if isinstance(content, dict) else {"text": content}
        with UnitOfWork() as uow:
            uow.session.add(
                KFMemory(
                    memory_id=mid,
                    organisation_id=organisation_id,
                    memory_type=memory_type,
                    content=payload,
                    scope=scope,
                    user_id=user_id,
                    agent_key=agent_key,
                    task_id=task_id,
                    workflow_id=workflow_id,
                    trust_level=trust_level,
                    provenance=provenance or {},
                )
            )
        bus.publish("memory.stored", {"memory_id": mid, "memory_type": memory_type}, organisation_id=organisation_id)
        return {"memory_id": mid, "memory_type": memory_type}

    def retrieve(self, memory_id: str, organisation_id: str) -> Optional[Dict[str, Any]]:
        with UnitOfWork() as uow:
            row = uow.session.get(KFMemory, memory_id)
            if not row or row.organisation_id != organisation_id:
                return None
            if row.status == "invalidated":
                return {"memory_id": memory_id, "status": "invalidated", "content": None}
            return {
                "memory_id": row.memory_id,
                "memory_type": row.memory_type,
                "content": row.content,
                "status": row.status,
                "trust_level": row.trust_level,
                "task_id": row.task_id,
                "version": row.version,
            }

    def search(
        self,
        organisation_id: str,
        *,
        memory_type: Optional[str] = None,
        query: Optional[str] = None,
        task_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        with UnitOfWork() as uow:
            q = uow.session.query(KFMemory).filter_by(organisation_id=organisation_id, status="active")
            if memory_type:
                q = q.filter_by(memory_type=memory_type)
            if task_id:
                q = q.filter_by(task_id=task_id)
            rows = q.order_by(KFMemory.created_at.desc()).limit(limit * 3).all()
            out = []
            for r in rows:
                if query and query.lower() not in str(r.content).lower():
                    continue
                out.append(
                    {
                        "memory_id": r.memory_id,
                        "memory_type": r.memory_type,
                        "content": r.content,
                        "task_id": r.task_id,
                        "trust_level": r.trust_level,
                    }
                )
                if len(out) >= limit:
                    break
            return out

    def update(self, memory_id: str, organisation_id: str, content: Any) -> Dict[str, Any]:
        with UnitOfWork() as uow:
            row = uow.session.get(KFMemory, memory_id)
            if not row or row.organisation_id != organisation_id:
                raise NotFoundError("Memory not found")
            row.content = content if isinstance(content, dict) else {"text": content}
            row.version = (row.version or 1) + 1
        bus.publish("memory.updated", {"memory_id": memory_id}, organisation_id=organisation_id)
        return {"memory_id": memory_id, "version": row.version}

    def invalidate(self, memory_id: str, organisation_id: str) -> None:
        with UnitOfWork() as uow:
            row = uow.session.get(KFMemory, memory_id)
            if not row or row.organisation_id != organisation_id:
                raise NotFoundError("Memory not found")
            row.status = "invalidated"
        bus.publish("memory.invalidated", {"memory_id": memory_id}, organisation_id=organisation_id)
