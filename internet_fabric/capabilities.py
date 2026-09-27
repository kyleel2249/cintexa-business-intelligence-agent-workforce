"""Internet capability contracts — agents receive only permitted ones."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class InternetCapability:
    capability_id: str
    name: str
    risk: str  # READ | WRITE | DESTRUCTIVE
    description: str
    required_permissions: List[str] = field(default_factory=list)


_CAP_SPECS = [
    ("web.search", "Web search", "READ", "Search the public web", ["web:search"]),
    ("web.open", "Open URL", "READ", "Open and retrieve a page", ["web:read"]),
    ("web.navigate", "Navigate", "READ", "Follow links within a session", ["web:read"]),
    ("web.click", "Click", "WRITE", "Click elements in authorized sessions", ["web:write"]),
    ("web.extract", "Extract content", "READ", "Extract text/structure from a page", ["web:read"]),
    ("web.find", "Find in page", "READ", "Search within retrieved page text", ["web:read"]),
    ("web.scroll", "Scroll", "READ", "Scroll page for lazy content", ["web:read"]),
    ("web.download", "Download", "READ", "Download permitted documents", ["web:download"]),
    ("web.pdf", "PDF intelligence", "READ", "Parse and cite PDF pages", ["web:read", "web:download"]),
    ("web.document", "Document retrieval", "READ", "Retrieve and parse office docs", ["web:read", "web:download"]),
    ("web.image", "Image intelligence", "READ", "Retrieve and analyze images", ["web:read"]),
    ("web.table", "Table extraction", "READ", "Extract tables from pages/docs", ["web:read"]),
    ("web.metadata", "Page metadata", "READ", "OpenGraph, JSON-LD, headers", ["web:read"]),
    ("web.api", "API invoke", "READ", "Call registered external APIs", ["web:api"]),
    ("web.form", "Form interaction", "WRITE", "Fill/submit permitted forms", ["web:write"]),
    ("web.monitor", "Change monitoring", "READ", "Monitor URL for changes", ["web:monitor"]),
    ("web.compare", "Source compare", "READ", "Compare multiple sources", ["web:research"]),
    ("web.verify", "Claim verify", "READ", "Verify claims against sources", ["web:research"]),
    ("web.crawl", "Controlled crawl", "READ", "Budgeted multi-page crawl", ["web:crawl"]),
    ("web.research", "Multi-step research", "READ", "Orchestrated research session", ["web:research"]),
    ("web.citation", "Citations", "READ", "Build citations from evidence", ["web:research"]),
    ("web.provenance", "Provenance", "READ", "Trace claim→evidence→source", ["web:research"]),
    ("web.archive", "Archive lookup", "READ", "Retrieve archived page versions", ["web:read"]),
    ("web.sitemap", "Sitemap", "READ", "Fetch and parse sitemaps", ["web:read"]),
    ("web.rss", "RSS/Atom", "READ", "Read public feeds", ["web:read"]),
    ("web.feed", "Feed", "READ", "Generic feed consumption", ["web:read"]),
    ("web.source_analysis", "Source quality", "READ", "Classify and score sources", ["web:research"]),
    ("web.entity_resolution", "Entity resolution", "READ", "Resolve named entities", ["web:research"]),
    ("web.change_detection", "Change detect", "READ", "Detect page content changes", ["web:monitor"]),
    ("web.content_classification", "Classify content", "READ", "Classify page content type", ["web:research"]),
    ("web.translation", "Translation", "READ", "Translate retrieved text", ["web:research"]),
    ("web.summarization", "Summarize", "READ", "Summarize retrieved content", ["web:research"]),
    ("web.media_analysis", "Media analysis", "READ", "Analyze video/audio from web", ["web:read"]),
    ("web.structured_extraction", "Structured extract", "READ", "JSON-LD, Schema.org, tables", ["web:read"]),
]

REGISTRY: Dict[str, InternetCapability] = {
    cid: InternetCapability(cid, name, risk, desc, perms)
    for cid, name, risk, desc, perms in _CAP_SPECS
}


def list_capabilities(risk: Optional[str] = None) -> List[dict]:
    out = []
    for c in REGISTRY.values():
        if risk and c.risk != risk:
            continue
        out.append({
            "capability_id": c.capability_id,
            "name": c.name,
            "risk": c.risk,
            "description": c.description,
            "required_permissions": list(c.required_permissions),
        })
    return out


def get_capability(capability_id: str) -> Optional[InternetCapability]:
    return REGISTRY.get(capability_id)


def has_capability(granted: List[str], needed: str) -> bool:
    return needed in granted or "*" in granted


# Back-compat alias for tests
INTERNET_CAPABILITIES = REGISTRY
