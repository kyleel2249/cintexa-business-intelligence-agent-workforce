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
| G09 | 4 | Path-only sandbox | HIGH | PARTIALLY MITIGATED | Real `unshare --net` network isolation now enforced (was previously a dead no-op parameter — verified live, traffic actually blocked); full container/seccomp isolation still requires runtime infra |
| G10 | 4 | Browser/computer providers | MED | INTENTIONALLY DEFERRED | Interfaces remain; real browser farm external |
| G11 | 3 | Vector ANN production | MED | INTENTIONALLY DEFERRED | Brute-force cosine scan confirmed (no pgvector/FAISS); previously-silent 5000-chunk cap now surfaced in response + logged, so truncation is visible instead of hidden. pgvector ops still external |
| G12 | 3 | PDF/DOCX ingestion | — | MITIGATED | Real parsers shipped (`knowledge_fabric/document_parsers.py`, `pypdf`+`python-docx`); verified end-to-end: real PDF/DOCX generated, ingested, extracted, and made searchable |
| G13 | 5 | Exactly-once | — | INTENTIONALLY BY DESIGN | At-least-once + idempotency |
| G14 | 6 | LLM judge as truth | — | INTENTIONALLY BY DESIGN | Deterministic evaluation |
| G15 | 7 | Uncontrolled self-mod | — | INTENTIONALLY BY DESIGN | Governance blocks |
| G16 | 6 | External OTEL | — | MITIGATED | Optional OTLP/HTTP exporter shipped (`observability/otlp_export.py`), feature-flagged via `OTEL_EXPORTER_OTLP_ENDPOINT`; verified live against a real local collector — span received correctly. No-op when unset (default), never blocks the app |
| G17 | X | Unified Pages+API deploy | MED | MITIGATED | Documented architecture; edge vs API roles |
| G18 | X | Full 194 agents | LOW | INTENTIONALLY DEFERRED | Registry scaling claim independently verified: 194 synthetic agents registered in 0.52s, no hardcoded limits found in register()/list_agents()/find_by_capability(). Remaining gap is writing ~182 agents' worth of real business logic — a content task, not infra |
| G19 | 5 | Global retry budgets | MED | MITIGATED | Job max_attempts + existing RetryBudget |
| G20 | X | Backup/restore tested | MED | PARTIALLY MITIGATED | Previous note overstated status — no procedure existed anywhere in the repo. Real tooling now shipped (`scripts/backup_restore.py`, `docs/BACKUP_RESTORE.md`); full drill (seed→backup→verify→simulate loss→restore→verify) run and passed for SQLite. Postgres path implemented but not drilled — no Postgres server available in this environment |
| G21 | X | DB schema never created on boot | CRITICAL | MITIGATED | Fresh deploy 500'd on every DB-backed endpoint — `lifespan()` never called `init_db()`, and neither `Procfile`/`start.sh`/`Dockerfile` ran migrations. Verified by booting cold and hitting `/bi/diagnostics` before and after fix. Now: `lifespan()` calls `init_db()` as a safety net, and `Procfile` release phase / `start.sh` / `Dockerfile` all run `alembic upgrade head` before serving traffic |
