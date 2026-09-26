# Gap Register — Phases 1–7 Production Hardening

Status legend: RESOLVED | MITIGATED | INTENTIONALLY DEFERRED | INTENTIONALLY BY DESIGN | BLOCKED

| gap_id | phase | component | severity | status | notes |
|--------|-------|-----------|----------|--------|-------|
| G01 | X | Process-local circuit/health | HIGH | MITIGATED | `cintexa_platform.coordination.DurableCircuit/Health` shared DB |
| G02 | X | Process-local freeze | HIGH | MITIGATED | Durable `plat_freeze` + process bridge |
| G03 | X | Multi-worker jobs | HIGH | MITIGATED | `plat_jobs` claim/lease/visibility timeout |
| G04 | X | Distributed leases | HIGH | MITIGATED | Fencing tokens on `plat_leases` |
| G05 | X | Canary = control plane only | HIGH | MITIGATED | `CanaryRouter` weighted/sticky routing |
| G06 | X | Browser long-lived API keys | HIGH | MITIGATED | `SecretVault` server-side; client redaction |
| G07 | 1 | SQLite as only DB | HIGH | MITIGATED | Postgres allowed; prod settings reject sqlite |
| G08 | 1 | Auth/dev fallback in prod | HIGH | MITIGATED | `validate_production_settings` fail-fast |
| G09 | 4 | Path-only sandbox | HIGH | INTENTIONALLY DEFERRED | Container/seccomp requires runtime infra |
| G10 | 4 | Browser/computer providers | MED | INTENTIONALLY DEFERRED | Interfaces remain; real browser farm external |
| G11 | 3 | Vector ANN production | MED | INTENTIONALLY DEFERRED | Embeddings abstraction; pgvector ops external |
| G12 | 3 | PDF/DOCX ingestion | MED | INTENTIONALLY DEFERRED | Explicit rejection remains until parsers ship |
| G13 | 5 | Exactly-once | — | INTENTIONALLY BY DESIGN | At-least-once + idempotency |
| G14 | 6 | LLM judge as truth | — | INTENTIONALLY BY DESIGN | Deterministic evaluation |
| G15 | 7 | Uncontrolled self-mod | — | INTENTIONALLY BY DESIGN | Governance blocks |
| G16 | 6 | External OTEL | MED | INTENTIONALLY DEFERRED | Internal telemetry first |
| G17 | X | Unified Pages+API deploy | MED | MITIGATED | Documented architecture; edge vs API roles |
| G18 | X | Full 194 agents | LOW | INTENTIONALLY DEFERRED | Registry scales; agents not bulk-loaded |
| G19 | 5 | Global retry budgets | MED | MITIGATED | Job max_attempts + existing RetryBudget |
| G20 | X | Backup/restore tested | MED | INTENTIONALLY DEFERRED | Documented procedure; needs ops environment |
