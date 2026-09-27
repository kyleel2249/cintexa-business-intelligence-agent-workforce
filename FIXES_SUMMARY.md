# CINTEXA BI Workforce — fix pass summary

Verified against a clean checkout: dependencies install cleanly, all `.py`
files byte-compile, and the app was actually booted (not just tested) to
confirm each bug before and after the fix.

## Test suite
`167/167` passing (was `148/167` on the original checkout).

## Files changed (9)

| File | Why |
|---|---|
| `tests/conftest.py` (new) | No `conftest.py` existed. 4 test files (`test_api.py`, `test_orchestrator.py`, `test_workforce_advanced.py`, `test_workforce_orchestrator.py`) never created the DB schema, so they failed with `no such table` on a clean run. Added a session-scoped fixture that initializes the schema, plus a self-healing `autouse` fixture — several other test modules repoint the global `DATABASE_URL`/engine to their own temp file and delete it on teardown without restoring prior state, which was silently breaking whichever file ran next alphabetically. |
| `database/session.py` | Added a safe `json_serializer` fallback (handles `datetime`, `date`, `time`, `Decimal`, `UUID`, `set`) on the SQLAlchemy engine. Root cause of several task-persistence crashes: agent code called `.model_dump()` on pydantic models with `datetime` fields without `mode="json"`, leaving raw `datetime` objects inside JSON columns, which Python's stdlib `json` can't serialize. This is defense-in-depth covering all 12 agents, not just the two fixed directly below. |
| `agents/diagnostic.py` | `report.model_dump()` → `report.model_dump(mode="json")`. `BusinessHealthReport.created_at` is a `datetime`; this was the direct trigger of `sqlalchemy.exc.StatementError` during task persistence. |
| `agents/research.py` | Same fix for `evidence.model_dump()` → `mode="json"` (evidence schema also carries `created_at`/`updated_at` datetimes). |
| `api/main.py` | **Critical fix.** `lifespan()` previously did nothing on startup. Verified by booting the app against a completely fresh SQLite file: `/health` returned 200 but `POST /bi/diagnostics` returned a raw 500 (`no such table: agent_tasks`), because neither `Procfile` nor `start.sh` ran any migration step. Added `init_db()` to startup as a safety net — it's `Base.metadata.create_all()`, which only creates missing tables, so it's a no-op against an already-migrated Postgres instance. |
| `Procfile` | Added a `release: alembic upgrade head` line (Heroku-style release phase) so migrations run before the web dyno takes traffic, per `docs/DEPLOYMENT_ARCHITECTURE.md`'s own stated intent ("Migrations run as a release job before traffic") — which wasn't actually implemented anywhere. |
| `Dockerfile` | Container path has no separate release phase, so `CMD` now runs `alembic upgrade head && exec uvicorn ...` inline before serving. |
| `start.sh` | Same migration step added for the local/manual run path. |
| `ui/assets/styles.css` | Found `styles.css` duplicated in both `assets/` (served by the Python app) and `ui/assets/` (Cloudflare Pages static deploy target). Confirmed it's dead code — unreferenced by any HTML/JS anywhere in the repo (`chat.css` and `dashboard.css` are the real, self-contained stylesheets actually loaded by `index.html`/`dashboard.html`). The two copies had silently drifted into two different color themes. Per your instruction not to delete anything, I did **not** remove the file — I reconciled `ui/assets/styles.css` to match the canonical `assets/styles.css` so the two deploy trees stop silently diverging. All 12 files shared between `assets/`/`ui/assets/` and root/`ui/` are now byte-identical again. |

## Verification performed (not just documented)
- `python3 -m py_compile` on every `.py` file in the repo — clean.
- `pip install -r requirements.txt` — clean.
- Full `pytest` run — 167/167 passing, stable across repeated clean runs.
- Booted `uvicorn api.main:app` against a **completely fresh** SQLite file (pre- and post-fix) and hit `/health` and `POST /bi/diagnostics` directly with `curl` to reproduce and then confirm the fix for the startup-schema bug.
- Ran `alembic upgrade head` against a fresh DB and diffed its resulting table set against `init_db()`'s — identical (89 tables both, plus Alembic's own `alembic_version` tracking table). Confirmed the migration chain (`001_phase1` → `009_ext`) is complete and correct.
- Byte-diffed every file shared between the root and `ui/` deployment trees to confirm they're now in sync.

## Not touched / still open
- `docs/GAP_REGISTER.md` items G09–G12, G16, G18, G20 are self-reported as intentionally deferred (container sandboxing, live browser farm, pgvector ops tuning, PDF/DOCX ingestion, external OTEL export, full 194-agent registry, backup/restore drill). I have not independently re-verified these; they require live infrastructure this sandbox doesn't have.

---

## Round 2: independently assessing and fixing the deferred gaps (G09–G20)

Rather than trust the register's self-reported status, each item below was independently re-verified against the actual code, and fixed where the fix didn't require infrastructure this sandbox doesn't have.

| Gap | Register said | What I found | Fix |
|---|---|---|---|
| **G09** — sandbox | "Path-only... container/seccomp requires runtime infra" | Worse than described: `network_disabled=True` (the default) was a **dead parameter** — never read anywhere in `run_process()`. Every sandboxed process ran with full network access regardless of the flag. | Implemented real network isolation via `unshare --net`, verified live: a `curl` inside the sandbox went from `200 OK` to unreachable (`exit=6`). Falls back with a loud warning (not silent) if `unshare` isn't available on the host. Full container/seccomp isolation genuinely still needs runtime infra — that part of the register's claim stands. |
| **G10** — browser/computer providers | "Interfaces remain; real browser farm external" | Accurate. Clean pluggable provider interface, `MockBrowserProvider` clearly labeled (`provider: "mock"` in every response) — no false claims anywhere. | No fix needed. |
| **G11** — vector ANN | "Embeddings abstraction; pgvector ops external" | Accurate that it's brute-force cosine scoring with no ANN index. Found an *undocumented* silent cliff: results are capped at 5000 chunks per org with zero signal when truncated. | Response now includes `candidate_pool_truncated`/`candidate_pool_size`/`candidate_pool_total`, plus a log warning. Real pgvector ops genuinely needs external infra — left deferred. |
| **G12** — PDF/DOCX ingestion | "Explicit rejection remains until parsers ship" | `python-docx` was already a declared dependency but **never imported anywhere in the codebase** — half-finished. This one doesn't need external infra, so I implemented it. | New `knowledge_fabric/document_parsers.py` with real PDF (`pypdf`) and DOCX (`python-docx`) extraction, wired into `ingest_document` via base64-encoded binary content. Verified end-to-end: generated a real PDF and DOCX with `reportlab`/`python-docx`, ingested both, and confirmed their content is chunked, embedded, and returned by an actual search query. Updated the one test that asserted the old rejection behavior; added real coverage. |
| **G16** — external OTEL | "Internal telemetry first" | Accurate — no OTEL/export path existed at all. | Added an optional, fire-and-forget OTLP/HTTP JSON exporter (`observability/otlp_export.py`), off by default, enabled via `OTEL_EXPORTER_OTLP_ENDPOINT`, runs in a background thread so a slow/dead collector can never affect request latency. **Verified live**: ran a real span through the actual `Tracer`, pointed it at a local mock HTTP collector, and confirmed the collector received the span with the correct name. |
| **G18** — full 194 agents | "Registry scales; agents not bulk-loaded" | Verified rather than trusted: registered 194 synthetic agents into `AgentOSRegistry` and confirmed `register()`/`list_agents()`/`find_by_capability()`/`select_agent()` have no hardcoded limits. Registered 194 agents in 0.52s. | No code fix — the actual gap is ~182 agents' worth of real business logic (a content task), not an infrastructure limitation. Register's claim confirmed accurate. |
| **G20** — backup/restore tested | "Documented procedure; needs ops environment" | This claim was **overstated** — no backup/restore procedure existed anywhere in the repo. `docs/RECOVERY.md` only covers in-process restart recovery (a different concern); `docs/PRODUCTION_READINESS.md` only listed it as an outstanding checklist item. | Wrote real, working tooling: `scripts/backup_restore.py` (SQLite via the safe online-backup API; Postgres via `pg_dump -Fc`/`pg_restore`) plus `docs/BACKUP_RESTORE.md`. **Ran a full drill end-to-end**: seeded real data → backed up → verified the backup → simulated total database loss (corrupted the file) → restored → confirmed the exact pre-disaster row came back. SQLite path is proven; Postgres path is implemented and follows standard practice but couldn't be drilled here (no Postgres server in this sandbox). |
| **G21** (new — not in original register) | — | Carried over from round 1: fresh deploys 500'd on every DB-backed endpoint because nothing ran migrations before serving traffic. | `lifespan()` now calls `init_db()`; `Procfile` gained a `release: alembic upgrade head` phase; `start.sh` and `Dockerfile` both run migrations before starting the server. Verified against the real Alembic-migrated schema, not just the `init_db()` safety net. |

`docs/GAP_REGISTER.md` itself has been updated in place to reflect verified status rather than self-reported status.

### Final verification
- Full suite: **169/169 passing** (was 148/167 at the start).
- All 5 real end-to-end drills in this round were actually executed, not just coded: network isolation, PDF/DOCX round-trip through real files, OTLP export to a real listening collector, 194-agent registry stress test, and a full backup/corrupt/restore/verify cycle.

