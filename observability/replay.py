"""Safe execution replay — default read-only / sandbox."""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.errors import AuthorizationError, ValidationError
from events.bus import bus
from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from observability.models_db import ObsReplay
from observability.tracing import tracer


DESTRUCTIVE_MODES_BLOCKED = {"PRODUCTION_WRITE", "LIVE_EXTERNAL_WRITE"}


class ReplayService:
    def create(
        self,
        organisation_id: str,
        *,
        source_execution_id: Optional[str] = None,
        source_trace_id: Optional[str] = None,
        mode: str = "READ_ONLY_REPLAY",
        payload: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        if mode in DESTRUCTIVE_MODES_BLOCKED:
            raise ValidationError(f"Replay mode not allowed: {mode}")
        rid = new_id("RPL-")
        with UnitOfWork() as uow:
            uow.session.add(
                ObsReplay(
                    replay_id=rid,
                    organisation_id=organisation_id,
                    source_execution_id=source_execution_id,
                    source_trace_id=source_trace_id,
                    mode=mode,
                    status="CREATED",
                    payload=payload or {},
                )
            )
        bus.publish("replay.created", {"replay_id": rid, "mode": mode}, organisation_id=organisation_id)
        return {"replay_id": rid, "mode": mode, "status": "CREATED"}

    def run_readonly(
        self,
        organisation_id: str,
        replay_id: str,
        *,
        inspect_fn=None,
    ) -> Dict[str, Any]:
        with UnitOfWork() as uow:
            row = uow.session.get(ObsReplay, replay_id)
            if not row or row.organisation_id != organisation_id:
                from core.errors import NotFoundError
                raise NotFoundError("Replay not found")
            if row.mode not in ("READ_ONLY_REPLAY", "EVALUATION_REPLAY", "SANDBOX_REPLAY", "MOCKED_EXTERNAL_REPLAY"):
                raise AuthorizationError("Unsafe replay mode")
            mode = row.mode
            source_trace = row.source_trace_id
            source_exec = row.source_execution_id

        # inspect only
        timeline = tracer.timeline(source_trace, organisation_id) if source_trace else {"spans": []}
        result = {
            "replay_id": replay_id,
            "mode": mode,
            "source_execution_id": source_exec,
            "source_trace_id": source_trace,
            "timeline": timeline,
            "side_effects": "none",
            "status": "COMPLETED",
        }
        if inspect_fn:
            result["inspection"] = inspect_fn(result)

        with UnitOfWork() as uow:
            row = uow.session.get(ObsReplay, replay_id)
            if row and row.organisation_id == organisation_id:
                row.status = "COMPLETED"
                row.result = result
        return result
