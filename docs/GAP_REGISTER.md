# Gap Register — Phases 1–7 Production Hardening

Status legend: RESOLVED | MITIGATED | PARTIALLY MITIGATED | BUILT, NOT INTEGRATED | INTENTIONALLY DEFERRED | INTENTIONALLY BY DESIGN | BLOCKED

## ⚠ Systemic finding (2026-09-27 independent re-assessment)

G01, G03, G04, G05, G06, and G19 were previously marked MITIGATED. Independent
verification found a consistent pattern across all six: the durability
mechanism (`cintexa_platform.coordination.DurableCircuit/Health`,
`cintexa_platform.workers.JobQueue`, `cintexa_platform.leases.DurableLease`,
`cintexa_platform.canary.CanaryRouter`, `cintexa_platform.vault.SecretVault`,
`reliability.retry.RetryBudget`) is real, migrated into the schema, and
passes its own unit tests in isolation — but has **zero callers anywhere in
the live request/task execution path** (`orchestrator/core.py`,
`agents/*.py`, `external_fabric/browser.py`). `api/main.py` exposes
read-only inspection endpoints (`/rel/health`, `/rel/dead-letters`) for some
of these, which will return empty/default data forever since nothing
populates them from real execution.

Concretely, as of this assessment: every agent task runs **synchronously,
in-process, on the request thread**, with no circuit breaker, no retry
budget enforcement, no job queue, no distributed lease, no canary-based
routing decision (`CanaryRouter.choose()` is called nowhere in the codebase,
tests included), and no secret vault involvement for outbound calls. This
is a materially different picture from "Phases 5–8 harden multi-worker
coordination" — those phases built the hardening layer but didn't connect
it to anything that needs hardening yet.

This is **not fixed in this pass** — wiring six subsystems into the live
orchestrator (adding circuit breakers around every agent invocation,
routing real work through the job queue, enforcing leases, making canary
routing decisions actually affect traffic, routing external API keys
through the vault) is a genuine architecture/integration project, not a
contained bug fix, and changing how the orchestrator executes tasks carries
real risk to currently-working synchronous behavior. It needs explicit
prioritization, not a silent change. See individual rows below for what was
verified for each.

| gap_id | phase | component | severity | status | notes |
|--------|-------|-----------|----------|--------|-------|
| G01 | X | Process-local circuit/health | HIGH | **BUILT, NOT INTEGRATED** | `DurableCircuit`/`DurableHealth` exist, migrated, and pass their own unit tests — but are instantiated **nowhere else in the codebase**, including `orchestrator/core.py`. No circuit breaker (process-local or durable) currently protects any live agent/tool invocation |
| G02 | X | Process-local freeze | HIGH | MITIGATED | Verified: `evolution.governance.change_freeze` genuinely bridges process-local state to the durable `DurableFreeze` on every freeze/unfreeze call. Scoped to change/deployment governance (self-modification proposals), not general task execution — that scope appears intentional, not a gap |
| G03 | X | Multi-worker jobs | HIGH | **BUILT, NOT INTEGRATED** | `cintexa_platform.workers.JobQueue` (enqueue/claim/lease) is fully implemented and migrated, but `.enqueue()` is called nowhere outside its own module — not by `orchestrator/core.py`, which runs every task synchronously in-process. There is no standalone worker process (`docs/DEPLOYMENT_ARCHITECTURE.md`'s "Workers" role has no `Procfile` entry or runnable entrypoint) |
| G04 | X | Distributed leases | HIGH | **BUILT, NOT INTEGRATED** | Same pattern as G01/G03 — `DurableLease`/fencing tokens exist and are migrated, but have zero callers outside `cintexa_platform/` itself |
| G05 | X | Canary = control plane only | HIGH | **BUILT, NOT INTEGRATED** | `CanaryRouter.upsert_route()` is called from `evolution/deployment.py`, but `CanaryRouter().choose()` — the actual routing decision — is called **nowhere in the entire codebase**, tests included. Canary routes can be registered but have zero effect on any live request |
| G06 | X | Browser long-lived API keys | HIGH | **BUILT, NOT INTEGRATED** | `SecretVault` is instantiated only in its own module (`vault = SecretVault()`) and its own unit test. `external_fabric/browser.py` (the code that would need to route API keys through it) never references it at all |
| G07 | 1 | SQLite as only DB | HIGH | MITIGATED | Postgres allowed; prod settings reject sqlite (mechanism verified — see G08) |
| G08 | 1 | Auth/dev fallback in prod | HIGH | PARTIALLY MITIGATED → MITIGATED | `validate_production_settings()` existed and was unit-tested in isolation but was **never actually called anywhere in the running app** — verified by booting with `ENVIRONMENT=production` + weak secret + `AUTH_DEV_FALLBACK=true` + sqlite: it booted and served traffic at 200 without complaint. Now wired into `lifespan()`, unguarded (not swallowed like the `init_db()` safety net) so a misconfigured prod deploy genuinely refuses to start. Re-verified: dangerous config now fails with `RuntimeError: PRODUCTION: secret_key must be set` before accepting any connections; normal dev boot unaffected |
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
| G19 | 5 | Global retry budgets | MED | **BUILT, NOT INTEGRATED** | `RetryBudget`/`reliability.circuit.circuits`/`reliability.health.health_registry` are real, migrated, and exposed via read-only inspection endpoints (`GET /rel/health`, `GET /rel/dead-letters`) — but nothing in `orchestrator/core.py` or `agents/*.py` ever consults `circuits` before an invocation, enforces a retry budget, or writes to `DeadLetterQueue` on a real task failure. The inspection endpoints will return empty/default data forever since nothing populates them from live execution |
| G20 | X | Backup/restore tested | MED | PARTIALLY MITIGATED | Previous note overstated status — no procedure existed anywhere in the repo. Real tooling now shipped (`scripts/backup_restore.py`, `docs/BACKUP_RESTORE.md`); full drill (seed→backup→verify→simulate loss→restore→verify) run and passed for SQLite. Postgres path implemented but not drilled — no Postgres server available in this environment |
| G21 | X | DB schema never created on boot | CRITICAL | MITIGATED | Fresh deploy 500'd on every DB-backed endpoint — `lifespan()` never called `init_db()`, and neither `Procfile`/`start.sh`/`Dockerfile` ran migrations. Verified by booting cold and hitting `/bi/diagnostics` before and after fix. Now: `lifespan()` calls `init_db()` as a safety net, and `Procfile` release phase / `start.sh` / `Dockerfile` all run `alembic upgrade head` before serving traffic |
| G22 | X | No real authentication — headers ARE identity | **CRITICAL** | **NOT FIXED — needs your decision** | `docs/AUTHORIZATION.md`/`core/auth.py` honestly document this as a known "Phase later" gap, but it is not tracked anywhere in this register and is more severe than its framing suggests. `get_org_and_user()` (the dependency every "authenticated" endpoint uses) has **zero verification** — it trusts the client-supplied `X-Organisation-Id`/`X-User-Id` headers as-is, with no password, token, session, or membership check, and never even reads `auth_dev_fallback`. **Live-proven**: created a task as org `acme-corp-CONFIDENTIAL`/user `alice`, then retrieved it as user `random-never-invited-attacker` using the same org header — 200 OK, full task content returned, including the literal request text. The per-request org-isolation check (`task.organisation_id != auth["organisation_id"]` → 403) does work correctly — confirmed a genuinely different org header is refused — but "which org you are" is entirely self-asserted. `python-jose`/`passlib[bcrypt]` are declared dependencies but never used anywhere; no real auth implementation exists to swap in. **Not attempted in this pass** — building real authentication (token issuance, session/credential verification, wiring it through every endpoint) is a product decision and a substantial feature, not a contained fix, and deserves explicit prioritization rather than a unilateral implementation buried in a hardening pass |
