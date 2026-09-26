"""Real canary traffic routing (weighted / sticky)."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional

from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from cintexa_platform.models_db import PlatformCanaryRoute


class CanaryRouter:
    def upsert_route(
        self,
        organisation_id: str,
        capability: str,
        *,
        baseline_version: str,
        candidate_version: str,
        percent: int,
        release_id: Optional[str] = None,
        sticky: bool = False,
    ) -> dict:
        percent = max(0, min(100, int(percent)))
        with UnitOfWork() as uow:
            row = (
                uow.session.query(PlatformCanaryRoute)
                .filter_by(organisation_id=organisation_id, capability=capability, status="ACTIVE")
                .first()
            )
            if row:
                row.baseline_version = baseline_version
                row.candidate_version = candidate_version
                row.percent = percent
                row.release_id = release_id
                row.sticky = sticky
                row.updated_at = datetime.utcnow()
                rid = row.route_id
            else:
                rid = new_id("CNY-")
                uow.session.add(
                    PlatformCanaryRoute(
                        route_id=rid,
                        organisation_id=organisation_id,
                        capability=capability,
                        baseline_version=baseline_version,
                        candidate_version=candidate_version,
                        percent=percent,
                        release_id=release_id,
                        sticky=sticky,
                        status="ACTIVE",
                    )
                )
        return {"route_id": rid, "percent": percent, "capability": capability}

    def choose(
        self,
        organisation_id: str,
        capability: str,
        *,
        subject_key: Optional[str] = None,
    ) -> dict:
        """Return which version to use. Uses sticky hash when subject_key set."""
        with UnitOfWork() as uow:
            row = (
                uow.session.query(PlatformCanaryRoute)
                .filter_by(organisation_id=organisation_id, capability=capability, status="ACTIVE")
                .first()
            )
            if not row or row.percent <= 0:
                return {
                    "version": row.baseline_version if row else "baseline",
                    "bucket": "baseline",
                    "percent": 0,
                }
            if row.percent >= 100:
                return {"version": row.candidate_version, "bucket": "candidate", "percent": 100}

            if subject_key:
                h = int(hashlib.sha256(f"{organisation_id}:{capability}:{subject_key}".encode()).hexdigest(), 16)
                bucket = h % 100
            else:
                import random
                bucket = random.randint(0, 99)

            if bucket < row.percent:
                return {
                    "version": row.candidate_version,
                    "bucket": "candidate",
                    "percent": row.percent,
                    "route_id": row.route_id,
                }
            return {
                "version": row.baseline_version,
                "bucket": "baseline",
                "percent": row.percent,
                "route_id": row.route_id,
            }

    def rollback(self, organisation_id: str, capability: str) -> dict:
        with UnitOfWork() as uow:
            rows = (
                uow.session.query(PlatformCanaryRoute)
                .filter_by(organisation_id=organisation_id, capability=capability, status="ACTIVE")
                .all()
            )
            for r in rows:
                r.status = "ROLLED_BACK"
                r.percent = 0
                r.updated_at = datetime.utcnow()
        return {"status": "ROLLED_BACK", "capability": capability}
