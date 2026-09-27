"""Search fabric — multi-provider with failover (Phase 5 style)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from events.bus import bus
from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from internet_fabric.models_db import InternetSearchLog
from internet_fabric.providers.base import ProviderSearchResult, SearchHit, SearchProvider
from internet_fabric.providers.mock_search import MockSearchProvider


@dataclass
class SearchResult:
    query: str
    status: str
    hits: List[SearchHit] = field(default_factory=list)
    providers_tried: List[str] = field(default_factory=list)
    fallback_used: bool = False
    latency_ms: float = 0.0
    logs: List[dict] = field(default_factory=list)


class SearchFabric:
    def __init__(self, providers: Optional[List[SearchProvider]] = None):
        self.providers = providers or [MockSearchProvider()]

    def search(
        self,
        organisation_id: str,
        query: str,
        *,
        research_id: Optional[str] = None,
        max_results: int = 10,
    ) -> SearchResult:
        t0 = time.perf_counter()
        tried: List[str] = []
        logs: List[dict] = []
        last: Optional[ProviderSearchResult] = None
        fallback = False

        for i, provider in enumerate(self.providers):
            tried.append(provider.name)
            if i > 0:
                fallback = True
            try:
                result = provider.search(query, max_results=max_results)
            except Exception as exc:
                result = ProviderSearchResult(
                    provider=provider.name,
                    query=query,
                    status="FAILED",
                    failure=str(exc)[:300],
                )
            last = result
            log_id = new_id("ISL-")
            with UnitOfWork() as uow:
                uow.session.add(
                    InternetSearchLog(
                        log_id=log_id,
                        organisation_id=organisation_id,
                        research_id=research_id,
                        provider=provider.name,
                        query=query,
                        status=result.status,
                        latency_ms=result.latency_ms,
                        result_count=len(result.hits),
                        failure=result.failure or "",
                        fallback_used=fallback,
                    )
                )
            logs.append(
                {
                    "log_id": log_id,
                    "provider": provider.name,
                    "status": result.status,
                    "result_count": len(result.hits),
                    "failure": result.failure,
                }
            )
            bus.publish(
                "internet.search.completed",
                {"provider": provider.name, "status": result.status, "query": query[:200]},
                organisation_id=organisation_id,
            )
            if result.status == "OK" and result.hits:
                return SearchResult(
                    query=query,
                    status="OK",
                    hits=result.hits,
                    providers_tried=tried,
                    fallback_used=fallback,
                    latency_ms=(time.perf_counter() - t0) * 1000,
                    logs=logs,
                )

        status = "FAILED" if last and last.status == "FAILED" else "EMPTY"
        return SearchResult(
            query=query,
            status=status,
            hits=last.hits if last else [],
            providers_tried=tried,
            fallback_used=fallback,
            latency_ms=(time.perf_counter() - t0) * 1000,
            logs=logs,
        )
