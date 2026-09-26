"""Failure taxonomy and classification."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class FailureCategory(str, Enum):
    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    AUTHORIZATION_FAILURE = "AUTHORIZATION_FAILURE"
    POLICY_DENIAL = "POLICY_DENIAL"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    NETWORK_FAILURE = "NETWORK_FAILURE"
    TIMEOUT = "TIMEOUT"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    RESOURCE_EXHAUSTION = "RESOURCE_EXHAUSTION"
    TRANSIENT_DATABASE_FAILURE = "TRANSIENT_DATABASE_FAILURE"
    PERMANENT_DATABASE_FAILURE = "PERMANENT_DATABASE_FAILURE"
    MODEL_FAILURE = "MODEL_FAILURE"
    TOOL_FAILURE = "TOOL_FAILURE"
    AGENT_FAILURE = "AGENT_FAILURE"
    WORKFLOW_FAILURE = "WORKFLOW_FAILURE"
    CANCELLATION = "CANCELLATION"
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"
    HUMAN_REQUIRED = "HUMAN_REQUIRED"


# Categories that may be retried (bounded)
RETRYABLE = {
    FailureCategory.RATE_LIMITED,
    FailureCategory.NETWORK_FAILURE,
    FailureCategory.TIMEOUT,
    FailureCategory.DEPENDENCY_FAILURE,
    FailureCategory.PROVIDER_FAILURE,
    FailureCategory.TRANSIENT_DATABASE_FAILURE,
    FailureCategory.MODEL_FAILURE,
    FailureCategory.TOOL_FAILURE,
    FailureCategory.RESOURCE_EXHAUSTION,
}

# Never retry
NON_RETRYABLE = {
    FailureCategory.VALIDATION_FAILURE,
    FailureCategory.AUTHORIZATION_FAILURE,
    FailureCategory.POLICY_DENIAL,
    FailureCategory.NOT_FOUND,
    FailureCategory.CONFLICT,
    FailureCategory.PERMANENT_DATABASE_FAILURE,
    FailureCategory.CANCELLATION,
    FailureCategory.HUMAN_REQUIRED,
}


@dataclass
class FailureDecision:
    category: FailureCategory
    retryable: bool
    retry_after_sec: float = 0.0
    max_retries: int = 0
    fallback_available: bool = False
    compensation_required: bool = False
    human_escalation: bool = False
    terminal: bool = False
    reason: str = ""
    details: dict = field(default_factory=dict)


def classify_failure(
    error: Any,
    *,
    attempt: int = 1,
    max_retries: int = 3,
    message: str = "",
) -> FailureDecision:
    """Map exceptions / messages to a FailureDecision."""
    from core.errors import (
        AuthorizationError,
        ConflictError,
        ExecutionError,
        NotFoundError,
        ValidationError,
    )

    msg = message or (str(error) if error else "")
    lower = msg.lower()

    if isinstance(error, ValidationError) or "validation" in lower or "missing required" in lower:
        cat = FailureCategory.VALIDATION_FAILURE
    elif isinstance(error, AuthorizationError) or "permission" in lower or "denied" in lower or "policy" in lower:
        if "policy" in lower:
            cat = FailureCategory.POLICY_DENIAL
        else:
            cat = FailureCategory.AUTHORIZATION_FAILURE
    elif isinstance(error, NotFoundError) or "not found" in lower:
        cat = FailureCategory.NOT_FOUND
    elif isinstance(error, ConflictError) or "conflict" in lower or "already" in lower:
        cat = FailureCategory.CONFLICT
    elif "rate limit" in lower or "429" in lower:
        cat = FailureCategory.RATE_LIMITED
    elif isinstance(error, (TimeoutError,)) or "timed out" in lower or "timeout" in lower:
        cat = FailureCategory.TIMEOUT
    elif isinstance(error, (ConnectionError, OSError, BrokenPipeError)) or "network" in lower or "connection" in lower or "dns" in lower or "transient" in lower:
        cat = FailureCategory.NETWORK_FAILURE
    elif "database" in lower or "sqlalchemy" in lower or "operationalerror" in lower:
        cat = FailureCategory.TRANSIENT_DATABASE_FAILURE
    elif "cancelled" in lower or "canceled" in lower:
        cat = FailureCategory.CANCELLATION
    elif isinstance(error, ExecutionError):
        cat = FailureCategory.TOOL_FAILURE
    else:
        cat = FailureCategory.UNKNOWN_FAILURE

    retryable = cat in RETRYABLE and attempt < max_retries
    human = cat == FailureCategory.HUMAN_REQUIRED or (
        not retryable and cat in (FailureCategory.UNKNOWN_FAILURE, FailureCategory.WORKFLOW_FAILURE) and attempt >= max_retries
    )
    terminal = (not retryable) or attempt >= max_retries

    retry_after = 0.0
    if retryable:
        if cat == FailureCategory.RATE_LIMITED:
            retry_after = min(60.0, 2.0 ** attempt)
        else:
            retry_after = min(30.0, 0.5 * (2 ** (attempt - 1)))

    return FailureDecision(
        category=cat,
        retryable=retryable,
        retry_after_sec=retry_after,
        max_retries=max_retries,
        fallback_available=cat in (FailureCategory.PROVIDER_FAILURE, FailureCategory.MODEL_FAILURE, FailureCategory.TOOL_FAILURE),
        compensation_required=False,
        human_escalation=human,
        terminal=terminal and not retryable,
        reason=msg[:500],
    )
