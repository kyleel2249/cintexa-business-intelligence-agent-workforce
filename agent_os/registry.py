"""Durable Agent Registry — register, lifecycle, capability discovery, versioning."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from core.errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from agent_os.lifecycle import (
    AgentLifecycleState,
    can_accept_new_work,
    can_continue_work,
    can_transition,
)
from agent_os.models_db import (
    AgentCapabilityIndex,
    RegisteredAgent,
)


class AgentOSRegistry:
    SYSTEM_ORG = "__system__"

    def register(
        self,
        *,
        organisation_id: str,
        agent_key: str,
        name: str,
        capabilities: List[str],
        version: str = "1.0.0",
        profile: Optional[Dict[str, Any]] = None,
        make_active: bool = True,
        actor: str = "system",
    ) -> RegisteredAgent:
        if not agent_key or not name:
            raise ValidationError("agent_key and name are required")
        capabilities = list(dict.fromkeys(capabilities or []))
        with UnitOfWork() as uow:
            existing = (
                uow.session.query(RegisteredAgent)
                .filter_by(organisation_id=organisation_id, agent_key=agent_key, version=version)
                .one_or_none()
            )
            if existing:
                raise ConflictError(f"Agent {agent_key}@{version} already registered")
            if make_active:
                # demote other active versions of same key
                for row in (
                    uow.session.query(RegisteredAgent)
                    .filter_by(organisation_id=organisation_id, agent_key=agent_key, is_active_version=True)
                    .all()
                ):
                    row.is_active_version = False
            agent = RegisteredAgent(
                id=new_id("AOS-"),
                organisation_id=organisation_id,
                agent_key=agent_key,
                name=name,
                version=version,
                is_active_version=make_active,
                lifecycle_state=AgentLifecycleState.REGISTERED.value,
                capabilities=capabilities,
                profile=profile or {},
            )
            uow.session.add(agent)
            uow.session.flush()
            for cap in capabilities:
                uow.session.add(
                    AgentCapabilityIndex(
                        id=new_id("CAP-"),
                        organisation_id=organisation_id,
                        capability=cap,
                        agent_id=agent.id,
                        agent_key=agent_key,
                        version=version,
                        enabled=True,
                    )
                )
            uow.audits.record(
                organisation_id=organisation_id,
                actor=actor,
                action="agent.register",
                resource_type="aos_agent",
                resource_id=agent.id,
                details={"agent_key": agent_key, "version": version},
            )
            uow.session.flush()
            uow.session.expunge(agent)
            return agent

    def get(self, agent_id: str, organisation_id: str) -> Optional[RegisteredAgent]:
        with UnitOfWork() as uow:
            row = uow.session.get(RegisteredAgent, agent_id)
            if not row or row.organisation_id != organisation_id:
                return None
            uow.session.expunge(row)
            return row

    def get_by_key(
        self, organisation_id: str, agent_key: str, *, version: Optional[str] = None
    ) -> Optional[RegisteredAgent]:
        with UnitOfWork() as uow:
            q = uow.session.query(RegisteredAgent).filter_by(
                organisation_id=organisation_id, agent_key=agent_key
            )
            if version:
                q = q.filter_by(version=version)
            else:
                q = q.filter_by(is_active_version=True)
            row = q.one_or_none()
            if row:
                uow.session.expunge(row)
            return row

    def list_agents(
        self, organisation_id: str, *, include_disabled: bool = True
    ) -> List[RegisteredAgent]:
        with UnitOfWork() as uow:
            q = uow.session.query(RegisteredAgent).filter_by(organisation_id=organisation_id)
            if not include_disabled:
                q = q.filter(RegisteredAgent.lifecycle_state != AgentLifecycleState.DISABLED.value)
            rows = q.order_by(RegisteredAgent.agent_key, RegisteredAgent.version).all()
            for r in rows:
                uow.session.expunge(r)
            return rows

    def set_lifecycle(
        self,
        agent_id: str,
        organisation_id: str,
        target: AgentLifecycleState,
        *,
        actor: str = "system",
    ) -> RegisteredAgent:
        with UnitOfWork() as uow:
            row = uow.session.get(RegisteredAgent, agent_id)
            if not row or row.organisation_id != organisation_id:
                raise NotFoundError(f"Agent {agent_id} not found")
            current = AgentLifecycleState(row.lifecycle_state)
            if not can_transition(current, target):
                raise ConflictError(f"Invalid transition {current.value} → {target.value}")
            row.lifecycle_state = target.value
            row.updated_at = datetime.utcnow()
            # disable capability index when disabled
            if target == AgentLifecycleState.DISABLED:
                for cap in (
                    uow.session.query(AgentCapabilityIndex).filter_by(agent_id=agent_id).all()
                ):
                    cap.enabled = False
            elif target == AgentLifecycleState.ACTIVE:
                for cap in (
                    uow.session.query(AgentCapabilityIndex).filter_by(agent_id=agent_id).all()
                ):
                    cap.enabled = True
            uow.audits.record(
                organisation_id=organisation_id,
                actor=actor,
                action="agent.lifecycle",
                resource_type="aos_agent",
                resource_id=agent_id,
                details={"from": current.value, "to": target.value},
            )
            uow.session.expunge(row)
            return row

    def activate(self, agent_id: str, organisation_id: str, actor: str = "system") -> RegisteredAgent:
        return self.set_lifecycle(agent_id, organisation_id, AgentLifecycleState.ACTIVE, actor=actor)

    def pause(self, agent_id: str, organisation_id: str, actor: str = "system") -> RegisteredAgent:
        return self.set_lifecycle(agent_id, organisation_id, AgentLifecycleState.PAUSED, actor=actor)

    def drain(self, agent_id: str, organisation_id: str, actor: str = "system") -> RegisteredAgent:
        return self.set_lifecycle(agent_id, organisation_id, AgentLifecycleState.DRAINING, actor=actor)

    def disable(self, agent_id: str, organisation_id: str, actor: str = "system") -> RegisteredAgent:
        return self.set_lifecycle(agent_id, organisation_id, AgentLifecycleState.DISABLED, actor=actor)

    def find_by_capability(
        self, organisation_id: str, capability: str, *, only_accepting_work: bool = True
    ) -> List[RegisteredAgent]:
        with UnitOfWork() as uow:
            caps = (
                uow.session.query(AgentCapabilityIndex)
                .filter_by(organisation_id=organisation_id, capability=capability, enabled=True)
                .all()
            )
            agent_ids = [c.agent_id for c in caps]
            if not agent_ids:
                return []
            rows = (
                uow.session.query(RegisteredAgent)
                .filter(RegisteredAgent.id.in_(agent_ids), RegisteredAgent.is_active_version == True)  # noqa: E712
                .all()
            )
            out = []
            for r in rows:
                state = AgentLifecycleState(r.lifecycle_state)
                if only_accepting_work and not can_accept_new_work(state):
                    continue
                uow.session.expunge(r)
                out.append(r)
            return out

    def select_agent(
        self, organisation_id: str, capability: str
    ) -> Optional[RegisteredAgent]:
        """Select best eligible agent: highest health, lowest in_flight."""
        candidates = self.find_by_capability(organisation_id, capability, only_accepting_work=True)
        if not candidates:
            return None
        candidates.sort(key=lambda a: (-(a.health_score or 0), a.in_flight or 0, a.failure_count or 0))
        return candidates[0]

    def record_health(
        self, agent_id: str, organisation_id: str, *, success: bool, error: Optional[str] = None
    ) -> None:
        with UnitOfWork() as uow:
            row = uow.session.get(RegisteredAgent, agent_id)
            if not row or row.organisation_id != organisation_id:
                return
            if success:
                row.success_count = (row.success_count or 0) + 1
            else:
                row.failure_count = (row.failure_count or 0) + 1
                row.last_error = error
            total = (row.success_count or 0) + (row.failure_count or 0)
            row.health_score = (row.success_count or 0) / total if total else 1.0
            row.updated_at = datetime.utcnow()

    def bootstrap_from_static_registry(self, organisation_id: str = "__system__") -> int:
        """Load static BI AGENT_REGISTRY into durable AOS for an org."""
        from agents.registry import AGENT_REGISTRY

        count = 0
        for key, profile in AGENT_REGISTRY.items():
            if key == "orchestrator":
                continue
            existing = self.get_by_key(organisation_id, key)
            if existing:
                continue
            caps = [c.name for c in (profile.capabilities or [])]
            if not caps:
                caps = [key]
            agent = self.register(
                organisation_id=organisation_id,
                agent_key=key,
                name=profile.name,
                capabilities=caps,
                version=getattr(profile, "version", "1.0.0") or "1.0.0",
                profile=profile.model_dump(mode="json") if hasattr(profile, "model_dump") else {},
            )
            self.activate(agent.id, organisation_id)
            count += 1
        return count
