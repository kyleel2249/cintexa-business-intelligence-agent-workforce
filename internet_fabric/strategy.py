"""Search strategy and query refinement."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


DEPTH_QUERY_BUDGET = {
    "SURFACE": 1,
    "STANDARD": 3,
    "DEEP": 6,
    "EXHAUSTIVE": 12,
}

DEPTH_PAGE_BUDGET = {
    "SURFACE": 2,
    "STANDARD": 5,
    "DEEP": 10,
    "EXHAUSTIVE": 25,
}


@dataclass
class QueryFamily:
    name: str
    query: str
    purpose: str


@dataclass
class ResearchPlan:
    depth: str
    primary: str
    families: List[QueryFamily] = field(default_factory=list)
    max_queries: int = 3
    max_pages: int = 5
    stop_reasons: List[str] = field(default_factory=list)


class SearchStrategyEngine:
    """Generate multi-family queries; no hard-coded domain allow-list required."""

    def plan(self, question: str, depth: str = "STANDARD", budget: Optional[Dict] = None) -> ResearchPlan:
        depth = (depth or "STANDARD").upper()
        if depth not in DEPTH_QUERY_BUDGET:
            depth = "STANDARD"
        budget = budget or {}
        max_q = int(budget.get("max_queries", DEPTH_QUERY_BUDGET[depth]))
        max_p = int(budget.get("max_pages", DEPTH_PAGE_BUDGET[depth]))
        q = (question or "").strip()
        families: List[QueryFamily] = [
            QueryFamily("primary", q, "Primary user question"),
        ]
        if depth in ("STANDARD", "DEEP", "EXHAUSTIVE"):
            families.append(QueryFamily("official", f"{q} official documentation", "Official sources"))
            families.append(QueryFamily("recent", f"{q} latest 2024 2025 2026", "Freshness"))
        if depth in ("DEEP", "EXHAUSTIVE"):
            families.append(QueryFamily("technical", f"{q} technical specification", "Technical"))
            families.append(QueryFamily("contrarian", f"{q} limitations risks criticism", "Contrarian"))
            families.append(QueryFamily("academic", f"{q} research study analysis", "Academic"))
        if depth == "EXHAUSTIVE":
            families.append(QueryFamily("historical", f"{q} history background", "Historical"))
            families.append(QueryFamily("alternatives", f"{q} alternatives comparison", "Alternatives"))
            families.append(QueryFamily("documents", f"{q} filetype:pdf report whitepaper", "Documents"))
        families = families[:max_q]
        return ResearchPlan(depth=depth, primary=q, families=families, max_queries=max_q, max_pages=max_p)

    def refine_after_gap(self, plan: ResearchPlan, gaps: List[str], used_queries: List[str]) -> List[str]:
        """Produce follow-up queries when evidence is insufficient."""
        extra: List[str] = []
        for gap in gaps[:3]:
            candidate = f"{plan.primary} {gap}".strip()
            if candidate and candidate not in used_queries:
                extra.append(candidate)
        if not extra and plan.primary:
            alt = f"{plan.primary} evidence sources data"
            if alt not in used_queries:
                extra.append(alt)
        return extra[: max(0, plan.max_queries - len(used_queries))]

    def should_stop(
        self,
        *,
        sources_ok: int,
        evidence_count: int,
        queries_used: int,
        max_queries: int,
        contradictions: int,
        depth: str,
    ) -> Optional[str]:
        if queries_used >= max_queries:
            return "budget_exhausted"
        if depth == "SURFACE" and sources_ok >= 1:
            return "surface_sufficient"
        if depth == "STANDARD" and sources_ok >= 2 and evidence_count >= 1:
            return "standard_sufficient"
        if depth == "DEEP" and sources_ok >= 3 and evidence_count >= 2 and contradictions == 0:
            return "deep_converged"
        if depth == "EXHAUSTIVE" and sources_ok >= 5 and evidence_count >= 3:
            return "exhaustive_coverage"
        return None
