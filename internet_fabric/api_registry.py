"""External API registry — schema-bound connectors (no live credentials required)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.errors import AuthorizationError, NotFoundError, ValidationError


@dataclass
class ExternalAPI:
    api_id: str
    name: str
    base_url: str
    organisation_id: str
    endpoints: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    auth_type: str = "none"  # none|bearer|header — credentials via vault later
    rate_limit_per_min: int = 30
    timeout_sec: float = 15.0
    enabled: bool = True
    permissions: List[str] = field(default_factory=lambda: ["web:api"])


class ExternalAPIRegistry:
    def __init__(self) -> None:
        self._apis: Dict[str, ExternalAPI] = {}

    def register(self, api: ExternalAPI) -> ExternalAPI:
        if not api.api_id or not api.base_url:
            raise ValidationError("api_id and base_url required")
        if not api.base_url.startswith("https://"):
            raise ValidationError("Only https base_url allowed")
        self._apis[api.api_id] = api
        return api

    def get(self, api_id: str, organisation_id: str) -> ExternalAPI:
        api = self._apis.get(api_id)
        if not api or api.organisation_id != organisation_id:
            raise NotFoundError(f"API not found: {api_id}")
        return api

    def list_for_org(self, organisation_id: str) -> List[dict]:
        return [
            {
                "api_id": a.api_id,
                "name": a.name,
                "base_url": a.base_url,
                "enabled": a.enabled,
                "endpoints": list(a.endpoints.keys()),
                "auth_type": a.auth_type,
            }
            for a in self._apis.values()
            if a.organisation_id == organisation_id
        ]

    def invoke_stub(self, api_id: str, organisation_id: str, endpoint: str, **kwargs) -> dict:
        """Safe stub: does not perform live HTTP. Records intent for future provider."""
        api = self.get(api_id, organisation_id)
        if not api.enabled:
            raise AuthorizationError("API disabled")
        if endpoint not in api.endpoints:
            raise ValidationError(f"Unknown endpoint: {endpoint}")
        return {
            "status": "NOT_EXECUTED",
            "reason": "Live API invoke requires configured provider and vault credentials",
            "api_id": api_id,
            "endpoint": endpoint,
            "blocked": True,
        }


default_api_registry = ExternalAPIRegistry()
