"""Transactional outbox foundation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from events.bus import bus
from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from reliability.models_db import RelOutbox, RelProcessedEvent


class Outbox:
    def enqueue(self, event_type: str, payload: Dict[str, Any], organisation_id: Optional[str] = None) -> str:
        oid = new_id("OBX-")
        with UnitOfWork() as uow:
            uow.session.add(
                RelOutbox(
                    outbox_id=oid,
                    organisation_id=organisation_id,
                    event_type=event_type,
                    payload=payload,
                    published=False,
                )
            )
        return oid

    def dispatch_pending(self, limit: int = 50) -> int:
        n = 0
        with UnitOfWork() as uow:
            rows = (
                uow.session.query(RelOutbox)
                .filter_by(published=False)
                .order_by(RelOutbox.created_at.asc())
                .limit(limit)
                .all()
            )
            for r in rows:
                bus.publish(r.event_type, r.payload, organisation_id=r.organisation_id)
                r.published = True
                r.published_at = datetime.utcnow()
                n += 1
        return n


class Inbox:
    def already_processed(self, consumer: str, event_id: str) -> bool:
        with UnitOfWork() as uow:
            row = (
                uow.session.query(RelProcessedEvent)
                .filter_by(consumer=consumer, event_id=event_id)
                .one_or_none()
            )
            return row is not None

    def mark_processed(self, consumer: str, event_id: str) -> None:
        if self.already_processed(consumer, event_id):
            return
        with UnitOfWork() as uow:
            uow.session.add(
                RelProcessedEvent(
                    id=new_id("PE-"),
                    consumer=consumer,
                    event_id=event_id,
                )
            )
