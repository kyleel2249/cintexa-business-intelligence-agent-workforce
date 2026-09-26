"""Mission store — database is authoritative; optional in-process cache."""

from __future__ import annotations

from typing import Dict, List, Optional

from schemas.missions import Mission, MissionStatus


class MissionManager:
    """
    Persist missions via MissionRepository.
    In-process cache is a performance aid only — DB remains source of truth.
    """

    def __init__(self) -> None:
        self._cache: Dict[str, Mission] = {}
        self._by_idempotency: Dict[str, str] = {}

    def save(self, mission: Mission) -> Mission:
        self._cache[mission.mission_id] = mission
        if mission.idempotency_key:
            self._by_idempotency[f"{mission.organisation_id}:{mission.idempotency_key}"] = (
                mission.mission_id
            )
        try:
            from persistence.unit_of_work import UnitOfWork

            with UnitOfWork() as uow:
                payload = mission.model_dump(mode="json")
                # Normalize enums to strings
                if isinstance(payload.get("status"), str) is False and payload.get("status"):
                    payload["status"] = str(payload["status"])
                uow.missions.save_payload(payload)
                # Mirror as workflow for recovery
                existing = uow.workflows.get(mission.mission_id, mission.organisation_id)
                status = mission.status.value if hasattr(mission.status, "value") else str(mission.status)
                if not existing:
                    uow.workflows.create(
                        workflow_id=mission.mission_id,
                        organisation_id=mission.organisation_id,
                        user_id=mission.user_id,
                        workflow_type="mission",
                        objective=mission.objective or "",
                        status=status,
                        current_state=status,
                        result=mission.result.model_dump(mode="json") if mission.result else {},
                        priority=mission.priority.value if hasattr(mission.priority, "value") else str(mission.priority),
                        idempotency_key=mission.idempotency_key,
                        metadata_json={"plan_version": mission.plan_version},
                    )
                else:
                    uow.workflows.update(
                        mission.mission_id,
                        mission.organisation_id,
                        status=status,
                        current_state=status,
                        result=mission.result.model_dump(mode="json") if mission.result else existing.result,
                        metadata_json={"plan_version": mission.plan_version},
                    )
                # Checkpoint of task states
                completed = [
                    t.task_id
                    for t in (mission.tasks or [])
                    if getattr(t.status, "value", str(t.status)) == "COMPLETED"
                ]
                pending = [
                    t.task_id
                    for t in (mission.tasks or [])
                    if getattr(t.status, "value", str(t.status))
                    in ("PENDING", "READY", "RUNNING", "BLOCKED")
                ]
                uow.checkpoints.create(
                    workflow_id=mission.mission_id,
                    organisation_id=mission.organisation_id,
                    completed_steps=completed,
                    pending_steps=pending,
                    state_refs={"plan_version": mission.plan_version, "status": status},
                    version=max(1, mission.plan_version or 1),
                )
                uow.audits.record(
                    organisation_id=mission.organisation_id,
                    actor=mission.user_id,
                    action="mission.save",
                    resource_type="mission",
                    resource_id=mission.mission_id,
                    details={"status": status},
                )
        except Exception:
            # Persistence failure must not wipe cache; re-raise in production paths
            # For durability guarantee we re-raise so callers know write failed
            raise
        return mission

    def get(self, mission_id: str) -> Optional[Mission]:
        if mission_id in self._cache:
            return self._cache[mission_id]
        try:
            from persistence.unit_of_work import UnitOfWork

            with UnitOfWork() as uow:
                # Search across orgs only by id for reload (caller must verify org)
                from database.models import MissionRecord

                row = uow.session.get(MissionRecord, mission_id)
                if not row or not row.payload:
                    return None
                mission = Mission.model_validate(row.payload)
                self._cache[mission_id] = mission
                return mission
        except Exception:
            return None

    def get_for_org(self, mission_id: str, organisation_id: str) -> Optional[Mission]:
        m = self.get(mission_id)
        if m and m.organisation_id != organisation_id:
            return None
        return m

    def get_by_idempotency(self, organisation_id: str, key: str) -> Optional[Mission]:
        mid = self._by_idempotency.get(f"{organisation_id}:{key}")
        if mid and mid in self._cache:
            return self._cache[mid]
        try:
            from persistence.unit_of_work import UnitOfWork

            with UnitOfWork() as uow:
                row = uow.missions.get_by_idempotency(organisation_id, key)
                if not row or not row.payload:
                    return None
                mission = Mission.model_validate(row.payload)
                self._cache[mission.mission_id] = mission
                self._by_idempotency[f"{organisation_id}:{key}"] = mission.mission_id
                return mission
        except Exception:
            return None

    def list_for_org(self, organisation_id: str, limit: int = 50) -> List[Mission]:
        try:
            from persistence.unit_of_work import UnitOfWork

            with UnitOfWork() as uow:
                rows = uow.missions.list_for_org(organisation_id, limit=limit)
                out = []
                for row in rows:
                    if row.payload:
                        m = Mission.model_validate(row.payload)
                        self._cache[m.mission_id] = m
                        out.append(m)
                return out
        except Exception:
            return [m for m in self._cache.values() if m.organisation_id == organisation_id][:limit]

    def update_status(self, mission_id: str, status: MissionStatus) -> Optional[Mission]:
        m = self.get(mission_id)
        if not m:
            return None
        m.status = status
        return self.save(m)

    def clear_cache(self) -> None:
        """Simulate process restart — drop in-memory state only."""
        self._cache.clear()
        self._by_idempotency.clear()


mission_manager = MissionManager()
