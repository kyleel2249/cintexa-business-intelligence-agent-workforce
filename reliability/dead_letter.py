"""Durable dead-letter queue."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from events.bus import bus
from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from reliability.models_db import RelDeadLetter


class DeadLetterQueue:
    def enqueue(
        self,
        *,
        organisation_id: str,
        reason: str,
        category: str = "UNKNOWN_FAILURE",
        source_type: str = "execution",
        source_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        attempts: int = 0,
        history: Optional[List] = None,
        payload: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        did = new_id("DL-")
        with UnitOfWork() as uow:
            row = RelDeadLetter(
                dead_letter_id=did,
                organisation_id=organisation_id,
                source_type=source_type,
                source_id=source_id,
                correlation_id=correlation_id,
                category=category,
                reason=reason,
                attempts=attempts,
                history=history or [],
                payload=payload or {},
                status="OPEN",
            )
            uow.session.add(row)
        bus.publish(
            "dead_letter.created",
            {"dead_letter_id": did, "category": category, "reason": reason[:200]},
            organisation_id=organisation_id,
        )
        return {"dead_letter_id": did, "status": "OPEN"}

    def list_open(self, organisation_id: str, limit: int = 50) -> List[Dict]:
        with UnitOfWork() as uow:
            rows = (
                uow.session.query(RelDeadLetter)
                .filter_by(organisation_id=organisation_id, status="OPEN")
                .order_by(RelDeadLetter.created_at.desc())
                .limit(limit)
                .all()
            )
            out = []
            for r in rows:
                out.append(
                    {
                        "dead_letter_id": r.dead_letter_id,
                        "category": r.category,
                        "reason": r.reason,
                        "attempts": r.attempts,
                        "source_id": r.source_id,
                        "status": r.status,
                    }
                )
            return out

    def reprocess(self, dead_letter_id: str, organisation_id: str) -> Dict[str, Any]:
        with UnitOfWork() as uow:
            row = uow.session.get(RelDeadLetter, dead_letter_id)
            if not row or row.organisation_id != organisation_id:
                from core.errors import NotFoundError
                raise NotFoundError("Dead letter not found")
            if row.status not in ("OPEN", "CLOSED"):
                from core.errors import ValidationError
                raise ValidationError(f"Cannot reprocess status {row.status}")
            row.status = "REPROCESSING"
            row.updated_at = datetime.utcnow()
            payload = dict(row.payload or {})
            hist = list(row.history or [])
            hist.append({"action": "reprocess", "at": datetime.utcnow().isoformat()})
            row.history = hist
            sid = row.source_id
        bus.publish(
            "dead_letter.reprocessed",
            {"dead_letter_id": dead_letter_id, "source_id": sid},
            organisation_id=organisation_id,
        )
        return {
            "dead_letter_id": dead_letter_id,
            "status": "REPROCESSING",
            "new_attempt": True,
            "source_id": sid,
            "payload": payload,
        }

    def close(self, dead_letter_id: str, organisation_id: str) -> Dict[str, Any]:
        with UnitOfWork() as uow:
            row = uow.session.get(RelDeadLetter, dead_letter_id)
            if not row or row.organisation_id != organisation_id:
                from core.errors import NotFoundError
                raise NotFoundError("Dead letter not found")
            row.status = "CLOSED"
            row.updated_at = datetime.utcnow()
        return {"dead_letter_id": dead_letter_id, "status": "CLOSED"}
