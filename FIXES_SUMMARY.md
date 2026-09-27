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
