# Phase 5 — Reliability & Failure Recovery

## Package `reliability/`

| Module | Role |
|--------|------|
| taxonomy | Failure categories + classify_failure |
| retry | RetryEngine, backoff, jitter, budgets |
| circuit | Per-dependency CircuitBreaker CLOSED/OPEN/HALF_OPEN |
| bulkhead | Concurrency pools |
| health | Dependency health + routing hint |
| dead_letter | Durable DLQ + reprocess |
| recovery | Workflow step recovery + compensation |
| outbox | Outbox + inbox duplicate protection |

## Failure categories

VALIDATION, AUTHORIZATION, POLICY_DENIAL, NOT_FOUND, CONFLICT, RATE_LIMITED,
NETWORK, TIMEOUT, DEPENDENCY, PROVIDER, RESOURCE_EXHAUSTION, TRANSIENT/PERMANENT_DB,
MODEL, TOOL, AGENT, WORKFLOW, CANCELLATION, UNKNOWN, HUMAN_REQUIRED

Non-retryable: validation, authz, policy, not_found, conflict, permanent DB, cancellation, human_required.

## Semantics

At-least-once with idempotency/DLQ — **not** exactly-once.

Recovery re-evaluates authorization at call sites; do not trust stale grants blindly.
