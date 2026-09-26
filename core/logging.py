"""Structured logging with correlation identifiers. Never log secrets."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

_SECRET_PATTERNS = [
    re.compile(r"(api[_-]?key|password|token|secret|authorization)\s*[:=]\s*\S+", re.I),
    re.compile(r"Bearer\s+\S+", re.I),
    re.compile(r"sk-[a-zA-Z0-9\-_]{10,}"),
    re.compile(r"sk-or-v1-[a-zA-Z0-9]+"),
]


def scrub(text: str) -> str:
    out = text
    for pat in _SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out


def get_logger(name: str = "cintexa") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] %(message)s"
            )
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def log_event(
    logger: logging.Logger,
    level: str,
    message: str,
    *,
    request_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    organisation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    task_id: Optional[str] = None,
    agent_execution_id: Optional[str] = None,
    **extra: Any,
) -> None:
    payload: Dict[str, Any] = {
        "msg": scrub(message),
        "request_id": request_id,
        "correlation_id": correlation_id,
        "organisation_id": organisation_id,
        "user_id": user_id,
        "workflow_id": workflow_id,
        "task_id": task_id,
        "agent_execution_id": agent_execution_id,
    }
    payload.update({k: v for k, v in extra.items() if v is not None})
    # Drop None keys for cleanliness
    payload = {k: v for k, v in payload.items() if v is not None}
    line = " ".join(f"{k}={v}" for k, v in payload.items())
    getattr(logger, level.lower(), logger.info)(line)
