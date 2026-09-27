"""Tenant-scoped research/search cache. Never cross-org."""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, Optional, Tuple


class TenantCache:
    def __init__(self, default_ttl_sec: float = 300.0):
        self._store: Dict[Tuple[str, str], Tuple[float, Any]] = {}
        self.default_ttl_sec = default_ttl_sec

    def _key(self, organisation_id: str, namespace: str, key: str) -> Tuple[str, str]:
        h = hashlib.sha256(f"{namespace}:{key}".encode()).hexdigest()
        return (organisation_id, h)

    def get(self, organisation_id: str, namespace: str, key: str) -> Optional[Any]:
        k = self._key(organisation_id, namespace, key)
        item = self._store.get(k)
        if not item:
            return None
        exp, val = item
        if time.time() > exp:
            self._store.pop(k, None)
            return None
        return val

    def set(self, organisation_id: str, namespace: str, key: str, value: Any, ttl_sec: Optional[float] = None) -> None:
        ttl = self.default_ttl_sec if ttl_sec is None else ttl_sec
        k = self._key(organisation_id, namespace, key)
        self._store[k] = (time.time() + ttl, value)

    def invalidate_org(self, organisation_id: str) -> int:
        rm = [k for k in self._store if k[0] == organisation_id]
        for k in rm:
            del self._store[k]
        return len(rm)


# Process-local cache instance (not authoritative; durable state is DB)
search_cache = TenantCache(default_ttl_sec=120.0)
