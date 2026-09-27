"""Internet capability contracts — agents receive only permitted ones."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class InternetCapability:
    capability_id: str
    name: str
    risk: str  # READ | WRITE | DESTRUCTIVE
    description: str
    required_permissions: List[str] = field(default_factory=list)


_CAPS = [
    ("web.search", "Web search", "READ", "Search the public web", ["web:search"]),
    ("web.open", "Open URL", "READ", "Open and retrieve a page", ["web:read"]),
    ("web.navigate", "Navigate", "READ", "Follow links within a session", ["web:read"]),
    ("web.extract", "Extract content", "READ", "Extract text/structure from a page", ["web:read"]),
    ("web.download", "Download", "READ", "Download permitted documents", ["web:download"]),
    ("web.pdf", "PDF intelligence", "READ", "Parse and cite PDF pages", ["web:read", "web:download"]),
    ("web.document", "Document retrieval", "READ", "Retrieve and parse office docs", ["web:read", "web:download"]),
    ("web.table", "Table extraction", "READ", "Extract tables from pages/docs", ["web:read"]),
    ("web.metadata", "Page metadata", "READ", "OpenGraph, JSON-LD, headers", ["web:read"]),
    ("web.api", "API invoke", "READ", "Call registered external APIs", ["web:api"]),
    ("web.monitor", "Change monitoring", "READ", "Monitor URL for changes", ["web:monitor"]),
    ("web.compare", "Source compare", "READ", "Compare multiple sources", ["web:research"]),
    ("web.verify", "Claim verify", "READ", "Verify claims against sources", ["web:research"]),
    ("web.research", "Multi-step research", "READ", "Orchestrated research session", ["web:research"]),
    ("web.citation", "Citations", "READ", "Build citations from evidence", ["web:research"]),
    ("web.provenance", "Provenance", "READ", "Trace claim→evidence→source", ["web:research"]),
    ("web.crawl", "Controlled crawl", "READ", "Budgeted multi-page crawl", ["web:crawl"]),
    ("web.form", "Form interaction", "WRITE", "Fill/submit permitted forms", ["web:write"]),
    ("web.source_analysis", "Source quality", "READ", "Classify and score sources", ["web:research"]),
    ("web.entity_resolution", "Entity resolution", "READ", "Resolve named entities", ["web:research"]),
    ("web.change_detection", "Change detect", "READ", "Detect page content changes", ["web:monitor"]),
    ("web.summarization", "Summarize", "READ", "Summarize retrieved content", ["web:read"]),
    ("web.media_analysis", "Media analysis", "READ", "Image/video/audio from web", ["media:analyze"]),
    ("web.structured_extraction", "Structured extract", "READ", "JSON-LD, Schema.org, feeds", ["web:read"]),
]

INTERNET_CAPABILITIES: Dict[str, InternetCapability] = {
    cid: InternetCapability(cid, name, risk, desc, perms)
    for cid, name, risk, desc, perms in _CAPS
}


def list_capabilities() -> List[dict]:
    return [
        {
            "capability_id": c.capability_id,
            "name": c.name,
            "risk": c.risk,
            "description": c.description,
            "required_permissions": list(c.required_permissions),
        }
        for c in INTERNET_CAPABILITIES.values()
    ]
