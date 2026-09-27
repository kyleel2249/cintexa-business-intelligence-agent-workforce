"""Deterministic mock search — no fabricated live web; fixtures only."""

from __future__ import annotations

import time
from typing import Dict, List

from internet_fabric.providers.base import ProviderSearchResult, SearchHit, SearchProvider


# Curated fixture corpus — tests and offline research demos
_CORPUS: List[Dict] = [
    {
        "title": "Example Domain",
        "url": "https://example.com/",
        "snippet": "This domain is for use in documentation examples.",
        "keywords": ["example", "documentation", "domain"],
        "category": "OFFICIAL_SOURCE",
    },
    {
        "title": "Example About",
        "url": "https://example.com/about",
        "snippet": "About the example domain used in standards documentation.",
        "keywords": ["example", "about", "standards"],
        "category": "OFFICIAL_SOURCE",
    },
    {
        "title": "Product overview",
        "url": "https://example.com/product",
        "snippet": "Our product is reliable and fast. Customers ask about pricing.",
        "keywords": ["product", "pricing", "customers", "reliable"],
        "category": "PROFESSIONAL_SOURCE",
    },
    {
        "title": "W3C HTML specification (fixture)",
        "url": "https://www.w3.org/TR/html/",
        "snippet": "HTML is the standard markup language for documents on the web.",
        "keywords": ["html", "web", "standard", "markup", "w3c"],
        "category": "TECHNICAL_DOCUMENTATION",
    },
    {
        "title": "RFC 3986 URI Generic Syntax (fixture)",
        "url": "https://www.rfc-editor.org/rfc/rfc3986",
        "snippet": "A Uniform Resource Identifier (URI) is a compact sequence of characters.",
        "keywords": ["uri", "url", "rfc", "internet", "identifier"],
        "category": "TECHNICAL_DOCUMENTATION",
    },
]


class MockSearchProvider(SearchProvider):
    name = "mock"

    def __init__(self, fail: bool = False):
        self.fail = fail

    def search(self, query: str, *, max_results: int = 10, **kwargs) -> ProviderSearchResult:
        t0 = time.perf_counter()
        if self.fail:
            return ProviderSearchResult(
                provider=self.name,
                query=query,
                status="FAILED",
                latency_ms=(time.perf_counter() - t0) * 1000,
                failure="provider_unavailable",
            )
        q = (query or "").lower()
        tokens = [t for t in q.replace(",", " ").split() if len(t) > 1]
        hits: List[SearchHit] = []
        for row in _CORPUS:
            score = sum(1 for t in tokens if t in row["keywords"] or t in row["title"].lower() or t in row["snippet"].lower())
            if score > 0 or not tokens:
                hits.append(
                    SearchHit(
                        title=row["title"],
                        url=row["url"],
                        snippet=row["snippet"],
                        source_name=row.get("category", ""),
                        score=float(score),
                        meta={"category": row.get("category")},
                    )
                )
        hits.sort(key=lambda h: h.score, reverse=True)
        hits = hits[:max_results]
        return ProviderSearchResult(
            provider=self.name,
            query=query,
            status="OK" if hits else "EMPTY",
            hits=hits,
            latency_ms=(time.perf_counter() - t0) * 1000,
        )
