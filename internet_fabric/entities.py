"""Entity resolution foundation for research findings."""

from __future__ import annotations

import re
from typing import Dict, List


_ENTITY_PATTERNS = [
    ("ORGANIZATION", re.compile(r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+){0,3}\s+(?:Inc|Corp|LLC|Ltd|Company|Group))\b")),
    ("PRODUCT", re.compile(r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+){0,2})\b")),
]


def extract_entities(text: str, max_entities: int = 20) -> List[Dict]:
    if not text:
        return []
    found: List[Dict] = []
    seen = set()
    for kind, pat in _ENTITY_PATTERNS:
        for m in pat.finditer(text[:8000]):
            name = m.group(1).strip()
            key = (kind, name.lower())
            if key in seen or len(name) < 3:
                continue
            seen.add(key)
            found.append({
                "entity_type": kind,
                "name": name,
                "confidence": 0.4,
                "method": "heuristic_regex",
                "note": "Low-confidence heuristic; not merged solely on similar names",
            })
            if len(found) >= max_entities:
                return found
    return found
