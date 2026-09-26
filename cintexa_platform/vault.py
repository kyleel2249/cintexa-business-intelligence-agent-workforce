"""Secret vault abstraction — never return secrets to browser clients."""

from __future__ import annotations

import os
from typing import Dict, Optional

from core.errors import AuthorizationError, NotFoundError


class SecretVault:
    """
    Dev: environment variables.
    Prod: plug HashiCorp Vault / cloud SM via subclass or env VAULT_BACKEND.
    Secrets are never serialized into API responses intended for browsers.
    """

    def __init__(self, prefix: str = "CINTEXA_SECRET_"):
        self.prefix = prefix
        self._mem: Dict[str, str] = {}

    def put(self, name: str, value: str, *, organisation_id: Optional[str] = None) -> dict:
        key = self._key(name, organisation_id)
        self._mem[key] = value
        # optional: write to env-backed store is process-local for dev
        return {"name": name, "stored": True, "backend": "memory"}

    def get(self, name: str, *, organisation_id: Optional[str] = None, allow_env: bool = True) -> str:
        key = self._key(name, organisation_id)
        if key in self._mem:
            return self._mem[key]
        if allow_env:
            env_key = f"{self.prefix}{name.upper()}"
            if env_key in os.environ:
                return os.environ[env_key]
            # common aliases
            aliases = {
                "openrouter_api_key": "OPENROUTER_API_KEY",
                "openai_api_key": "OPENAI_API_KEY",
                "database_url": "DATABASE_URL",
            }
            if name in aliases and aliases[name] in os.environ:
                return os.environ[aliases[name]]
        raise NotFoundError(f"Secret not found: {name}")

    def get_for_server(self, name: str, organisation_id: Optional[str] = None) -> str:
        """Server-side only retrieval."""
        return self.get(name, organisation_id=organisation_id)

    def redact_for_client(self, data: dict) -> dict:
        from observability.logging import redact_secrets
        return redact_secrets(data)

    def rotate(self, name: str, new_value: str, organisation_id: Optional[str] = None) -> dict:
        self.put(name, new_value, organisation_id=organisation_id)
        return {"name": name, "rotated": True}

    def _key(self, name: str, organisation_id: Optional[str]) -> str:
        return f"{organisation_id or '_'}::{name}"


vault = SecretVault()
