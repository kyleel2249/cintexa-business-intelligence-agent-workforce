"""Result cache with TTL, scope, and confidence."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional


class ResultCache:
    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}

    def _key(self, scope: str, name: str) -> str:
        return f"{scope}::{name}"

    def set(
        self,
        scope: str,
        name: str,
        value: Any,
        *,
        ttl_seconds: int = 3600,
        source: str = "",
        confidence: float = 0.7,
        version: str = "1",
    ) -> None:
        self._store[self._key(scope, name)] = {
            "value": value,
            "created_at": time.time(),
            "expires_at": time.time() + ttl_seconds,
            "source": source,
            "confidence": confidence,
            "version": version,
            "scope": scope,
        }

    def get(self, scope: str, name: str) -> Optional[Any]:
        entry = self._store.get(self._key(scope, name))
        if not entry:
            return None
        if time.time() > entry["expires_at"]:
            del self._store[self._key(scope, name)]
            return None
        return entry["value"]

    def get_entry(self, scope: str, name: str) -> Optional[Dict[str, Any]]:
        entry = self._store.get(self._key(scope, name))
        if not entry:
            return None
        if time.time() > entry["expires_at"]:
            del self._store[self._key(scope, name)]
            return None
        return entry


result_cache = ResultCache()
