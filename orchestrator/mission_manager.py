"""In-memory mission store with idempotency (DB-ready interface)."""

from __future__ import annotations

from typing import Dict, List, Optional

from schemas.missions import Mission, MissionStatus


class MissionManager:
    def __init__(self) -> None:
        self._missions: Dict[str, Mission] = {}
        self._by_idempotency: Dict[str, str] = {}

    def save(self, mission: Mission) -> Mission:
        self._missions[mission.mission_id] = mission
        if mission.idempotency_key:
            self._by_idempotency[f"{mission.organisation_id}:{mission.idempotency_key}"] = (
                mission.mission_id
            )
        return mission

    def get(self, mission_id: str) -> Optional[Mission]:
        return self._missions.get(mission_id)

    def get_by_idempotency(self, organisation_id: str, key: str) -> Optional[Mission]:
        mid = self._by_idempotency.get(f"{organisation_id}:{key}")
        return self._missions.get(mid) if mid else None

    def list_for_org(self, organisation_id: str, limit: int = 50) -> List[Mission]:
        items = [m for m in self._missions.values() if m.organisation_id == organisation_id]
        items.sort(key=lambda m: m.created_at, reverse=True)
        return items[:limit]

    def update_status(self, mission_id: str, status: MissionStatus) -> Optional[Mission]:
        m = self._missions.get(mission_id)
        if not m:
            return None
        m.status = status
        return m


mission_manager = MissionManager()
