"""Provider interfaces — architecture independent of a single search vendor."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str = ""
    published_at: Optional[str] = None
    source_name: str = ""
    score: float = 0.0
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderSearchResult:
    provider: str
    query: str
    status: str  # OK|FAILED|EMPTY
    hits: List[SearchHit] = field(default_factory=list)
    latency_ms: float = 0.0
    failure: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


class SearchProvider(ABC):
    name: str = "base"

    @abstractmethod
    def search(self, query: str, *, max_results: int = 10, **kwargs) -> ProviderSearchResult:
        ...

    def news(self, query: str, *, max_results: int = 10, **kwargs) -> ProviderSearchResult:
        return self.search(query, max_results=max_results, **kwargs)

    def documents(self, query: str, *, max_results: int = 10, **kwargs) -> ProviderSearchResult:
        return self.search(query, max_results=max_results, **kwargs)
