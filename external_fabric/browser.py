"""Browser engine — session lifecycle + provider-neutral operations."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from core.errors import AuthorizationError, NotFoundError, ValidationError
from events.bus import bus
from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from external_fabric.url_security import UrlPolicy, validate_url
from external_fabric.governor import InteractionGovernor
from external_fabric.models_db import ExtBrowserSession, ExtPageObservation, ExtAction
from external_fabric.providers.mock import MockBrowserProvider


class BrowserSession:
    def __init__(self, row: dict, engine: "BrowserEngine"):
        self.data = row
        self.engine = engine

    @property
    def session_id(self) -> str:
        return self.data["session_id"]


class BrowserEngine:
    def __init__(self, provider=None):
        self.provider = provider or MockBrowserProvider()
        self.governor = InteractionGovernor()

    def create_session(
        self,
        organisation_id: str,
        *,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        allowed_domains: Optional[List[str]] = None,
        ttl_sec: int = 3600,
    ) -> dict:
        sid = new_id("BS-")
        with UnitOfWork() as uow:
            uow.session.add(
                ExtBrowserSession(
                    session_id=sid,
                    organisation_id=organisation_id,
                    agent_id=agent_id,
                    task_id=task_id,
                    provider=getattr(self.provider, "name", "mock"),
                    status="READY",
                    allowed_domains=allowed_domains or [],
                    expires_at=datetime.utcnow() + timedelta(seconds=ttl_sec),
                )
            )
        bus.publish("browser.session.created", {"session_id": sid}, organisation_id=organisation_id)
        return {"session_id": sid, "status": "READY", "provider": getattr(self.provider, "name", "mock")}

    def _get(self, session_id: str, organisation_id: str) -> ExtBrowserSession:
        with UnitOfWork() as uow:
            row = uow.session.get(ExtBrowserSession, session_id)
            if not row or row.organisation_id != organisation_id:
                raise NotFoundError("Browser session not found")
            if row.status == "CLOSED":
                raise ValidationError("Session closed")
            return row

    def navigate(
        self,
        session_id: str,
        organisation_id: str,
        url: str,
        *,
        permissions: Optional[Set[str]] = None,
    ) -> dict:
        decision = self.governor.evaluate(
            organisation_id=organisation_id,
            capability_id="WEB_OPEN_URL",
            target=url,
            permissions=permissions or {"web:read", "web:search", "web:research", "*"},
        )
        if decision.decision in ("BLOCK", "REJECT"):
            return {"status": decision.decision, "reason": decision.reason}

        with UnitOfWork() as uow:
            row = uow.session.get(ExtBrowserSession, session_id)
            if not row or row.organisation_id != organisation_id:
                raise NotFoundError("Browser session not found")
            allowed = set(row.allowed_domains or [])
            policy = UrlPolicy(
                allow_http=False,
                allowed_domains=allowed if allowed else None,
            )
            safe_url = validate_url(url, policy)
            row.status = "NAVIGATING"
            row.current_url = safe_url

        result = self.provider.navigate(safe_url)
        if result.get("status") == "CAPTCHA_DETECTED":
            with UnitOfWork() as uow:
                row = uow.session.get(ExtBrowserSession, session_id)
                if row:
                    row.status = "BLOCKED"
                    row.meta = {**(row.meta or {}), "captcha": True}
            return {"status": "CAPTCHA_DETECTED", "url": safe_url}

        with UnitOfWork() as uow:
            row = uow.session.get(ExtBrowserSession, session_id)
            if row:
                row.status = "READY"
                row.current_url = safe_url
        bus.publish("page.opened", {"session_id": session_id, "url": safe_url}, organisation_id=organisation_id)
        return result

    def observe(self, session_id: str, organisation_id: str, url: Optional[str] = None) -> dict:
        with UnitOfWork() as uow:
            row = uow.session.get(ExtBrowserSession, session_id)
            if not row or row.organisation_id != organisation_id:
                raise NotFoundError("Browser session not found")
            target = url or row.current_url
            if not target:
                raise ValidationError("No URL to observe")
            allowed = set(row.allowed_domains or [])
        policy = UrlPolicy(allowed_domains=allowed if allowed else None)
        safe = validate_url(target, policy)
        obs = self.provider.observe(safe)
        # Mark external content untrusted
        obs["trust"] = "EXTERNAL_UNTRUSTED"
        obs["is_instruction"] = False  # DATA not instructions
        oid = new_id("PO-")
        with UnitOfWork() as uow:
            uow.session.add(
                ExtPageObservation(
                    observation_id=oid,
                    organisation_id=organisation_id,
                    session_id=session_id,
                    url=safe,
                    title=obs.get("title") or "",
                    content_hash=obs.get("content_hash"),
                    observation=obs,
                    trust="EXTERNAL_UNTRUSTED",
                )
            )
        bus.publish("page.observed", {"observation_id": oid, "url": safe}, organisation_id=organisation_id)
        return {"observation_id": oid, **obs}

    def close(self, session_id: str, organisation_id: str) -> dict:
        with UnitOfWork() as uow:
            row = uow.session.get(ExtBrowserSession, session_id)
            if not row or row.organisation_id != organisation_id:
                raise NotFoundError("Browser session not found")
            row.status = "CLOSED"
            row.closed_at = datetime.utcnow()
        bus.publish("browser.session.closed", {"session_id": session_id}, organisation_id=organisation_id)
        return {"session_id": session_id, "status": "CLOSED"}
