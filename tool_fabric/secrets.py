"""Secret provider abstraction — references only; never return raw secrets to agents."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class SecretRef:
    name: str
    organisation_id: str
    expires_at: Optional[str] = None


class SecretProvider:
    """Maps secret names to values for injection into sandboxed env only."""

    def __init__(self):
        self._store: Dict[str, Dict[str, str]] = {}  # org -> name -> value

    def put(self, organisation_id: str, name: str, value: str) -> SecretRef:
        self._store.setdefault(organisation_id, {})[name] = value
        return SecretRef(name=name, organisation_id=organisation_id)

    def resolve_for_execution(
        self, organisation_id: str, names: list, *, inject: bool = True
    ) -> Dict[str, str]:
        """Return env mapping for sandbox. Does not expose values outside execution."""
        if not inject:
            return {}
        org = self._store.get(organisation_id, {})
        out = {}
        for n in names or []:
            if n in org:
                out[n] = org[n]
            elif n in os.environ and not any(
                s in n.upper() for s in ("SECRET", "PASSWORD", "TOKEN", "API_KEY", "PRIVATE")
            ):
                # only non-sensitive public config from process env by explicit name
                out[n] = os.environ[n]
        return out

    def redact(self, text: str, organisation_id: str) -> str:
        org = self._store.get(organisation_id, {})
        out = text or ""
        for name, val in org.items():
            if val and val in out:
                out = out.replace(val, f"[REDACTED:{name}]")
        return out
