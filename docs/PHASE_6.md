# Phase 6 — Observability, Evaluation & Continuous QA

## Package `observability/`

| Module | Role |
|--------|------|
| context | Correlation IDs + span context |
| logging | Structured logs + secret redaction |
| metrics | Counters + histograms (p50/p95/p99), low cardinality |
| tracing | Spans, timelines |
| store | Durable org-scoped telemetry |
| evaluation | Datasets, deterministic eval, regression, quality profiles, defects |
| replay | Safe READ_ONLY / SANDBOX replay |
| alerts | Alert + incident foundation |

## Principles

- Not a second source of truth for tasks/workflows
- Tenant isolation on all reads
- Secrets redacted
- UNKNOWN ≠ PASS
- LLM-judge not implemented as override of deterministic FAIL
- Replay defaults to non-destructive modes

## API

- GET `/bi/obs/traces/{trace_id}`
- GET `/bi/obs/metrics`
- GET `/bi/obs/logs`
- GET `/bi/obs/alerts`
- POST `/bi/obs/eval/datasets`
- POST `/bi/obs/eval/run`
