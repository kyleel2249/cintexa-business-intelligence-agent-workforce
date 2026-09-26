"""CINTEXA Reliability & Failure Recovery (Phase 5)."""

from reliability.taxonomy import FailureCategory, classify_failure, FailureDecision
from reliability.retry import RetryEngine, RetryPolicy
from reliability.circuit import CircuitBreaker, CircuitState
from reliability.health import HealthRegistry, HealthStatus
from reliability.dead_letter import DeadLetterQueue
from reliability.recovery import RecoveryService

__all__ = [
    "FailureCategory",
    "classify_failure",
    "FailureDecision",
    "RetryEngine",
    "RetryPolicy",
    "CircuitBreaker",
    "CircuitState",
    "HealthRegistry",
    "HealthStatus",
    "DeadLetterQueue",
    "RecoveryService",
]
