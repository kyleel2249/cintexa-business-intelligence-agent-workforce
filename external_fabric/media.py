"""Media analysis pipeline (transcription etc.) via provider."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from events.bus import bus
from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from external_fabric.models_db import ExtMediaJob
from external_fabric.providers.mock import MockBrowserProvider
from external_fabric.url_security import validate_url, UrlPolicy


class MediaEngine:
    def __init__(self, provider=None):
        self.provider = provider or MockBrowserProvider()

    def analyze_video(self, organisation_id: str, source_url: str) -> dict:
        validate_url(source_url, UrlPolicy())
        jid = new_id("MED-")
        with UnitOfWork() as uow:
            uow.session.add(
                ExtMediaJob(
                    job_id=jid,
                    organisation_id=organisation_id,
                    media_type="video",
                    source_url=source_url,
                    status="RUNNING",
                )
            )
        bus.publish("media.analysis.started", {"job_id": jid}, organisation_id=organisation_id)
        result = self.provider.transcribe_video(source_url)
        result["trust"] = "EXTERNAL_UNTRUSTED"
        with UnitOfWork() as uow:
            row = uow.session.get(ExtMediaJob, jid)
            if row:
                row.status = "COMPLETED"
                row.result = result
                row.completed_at = datetime.utcnow()
        bus.publish("media.analysis.completed", {"job_id": jid}, organisation_id=organisation_id)
        return {"job_id": jid, "status": "COMPLETED", "result": result}
