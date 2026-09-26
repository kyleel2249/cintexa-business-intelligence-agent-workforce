"""Structured logging with secret redaction."""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, Optional

from observability.context import get_context

_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|password|secret|authorization)\s*[:=]\s*['\"]?([^\s'\"]+)", re.I),
    re.compile(r"\b(sk-[a-zA-Z0-9\-]{10,})\b"),
    re.compile(r"\b(ghp_[a-zA-Z0-9]{20,})\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/=]+"),
    re.compile(r"(?i)\b(API_KEY|SECRET|PASSWORD|TOKEN|PRIVATE_KEY|DATABASE_PASSWORD|SESSION_TOKEN)[_-]TEST[_A-Za-z0-9]*"),
    re.compile(r"(?i)\b(API_KEY_TEST|SECRET_TEST|PASSWORD_TEST|BEARER_TOKEN_TEST|PRIVATE_KEY_TEST|DATABASE_PASSWORD_TEST|SESSION_TOKEN_TEST)[_A-Za-z0-9]*"),
]

_SENSITIVE_KEYS = {
    "api_key", "apikey", "token", "password", "secret", "authorization",
    "access_token", "refresh_token", "private_key", "credential", "cookie",
}


def redact_secrets(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if str(k).lower() in _SENSITIVE_KEYS or any(s in str(k).lower() for s in ("secret", "password", "token", "api_key")):
                out[k] = "[REDACTED]"
            else:
                out[k] = redact_secrets(v)
        return out
    if isinstance(obj, list):
        return [redact_secrets(x) for x in obj]
    if isinstance(obj, str):
        s = obj
        for pat in _SECRET_PATTERNS:
            s = pat.sub(lambda m: m.group(0)[: m.start(2) - m.start(0)] + "[REDACTED]" if m.lastindex and m.lastindex >= 2 else "[REDACTED]", s)
        # simpler second pass
        s = re.sub(r"\bsk-[a-zA-Z0-9\-]{10,}\b", "[REDACTED]", s)
        s = re.sub(r"\bghp_[a-zA-Z0-9]{20,}\b", "[REDACTED]", s)
        return s
    return obj


def structured_log(
    level: str,
    message: str,
    *,
    component: str = "app",
    status: Optional[str] = None,
    error: Optional[str] = None,
    duration_ms: Optional[float] = None,
    metadata: Optional[Dict] = None,
    organisation_id: Optional[str] = None,
) -> Dict[str, Any]:
    ctx = get_context()
    record = {
        "timestamp": time.time(),
        "severity": level.upper(),
        "message": redact_secrets(message) if isinstance(message, str) else message,
        "component": component,
        "status": status,
        "error": redact_secrets(error) if error else None,
        "duration_ms": duration_ms,
        "metadata": redact_secrets(metadata or {}),
    }
    if ctx:
        record.update({k: v for k, v in ctx.to_dict().items() if v is not None})
    if organisation_id:
        record["organisation_id"] = organisation_id
    # durable append
    try:
        from observability.store import TelemetryStore
        TelemetryStore().append_log(record)
    except Exception:
        pass  # telemetry must not break primary path
    return record
