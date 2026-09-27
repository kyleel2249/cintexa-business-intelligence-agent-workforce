"""Global pytest fixtures shared by every test module.

Gap fixed here
--------------
`tests/test_api.py`, `tests/test_orchestrator.py`,
`tests/test_workforce_advanced.py` and `tests/test_workforce_orchestrator.py`
exercise the application through `api/main.py` / `orchestrator/core.py`,
both of which use the *default* SQLAlchemy engine
(`database.session.get_engine()` with no explicit URL). None of those four
files ever call `database.session.init_db()`, so on a clean checkout the
`agent_tasks` table (and every other core table) does not exist yet.

Every other test file in this suite already works around this by opening
its own temporary SQLite file and calling `init_db()` at import time (see
`tests/test_phase1_persistence.py` for the canonical pattern) — this file
generalises that same pattern to a single, session-scoped, autouse fixture
so *every* test module gets a fully-migrated, isolated database regardless
of import/collection order, without editing any existing test file.
"""

from __future__ import annotations

import os
import tempfile

import pytest

# Isolated SQLite file for the whole test session. Created once, at import
# time, so DATABASE_URL is pinned before any application module has a
# chance to lazily instantiate (and cache) the default engine.
_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_DB.close()
_SESSION_URL = f"sqlite:///{_DB.name}"
os.environ.setdefault("DATABASE_URL", _SESSION_URL)


def _pin_session_db() -> None:
    """(Re-)point the global engine at this session's schema-complete DB."""
    from database.session import init_db, reset_engine
    import config.settings as settings_mod

    os.environ["DATABASE_URL"] = _SESSION_URL
    if hasattr(settings_mod.get_settings, "cache_clear"):
        settings_mod.get_settings.cache_clear()
    reset_engine()
    init_db(_SESSION_URL)


@pytest.fixture(scope="session", autouse=True)
def _global_db_schema():
    """Create every registered table on the default engine before tests run."""
    _pin_session_db()

    yield

    from database.session import reset_engine

    reset_engine()
    try:
        os.unlink(_DB.name)
    except OSError:
        pass


@pytest.fixture(autouse=True)
def _heal_default_db_state():
    """Self-heal process-global DB state before every test.

    Several test modules (e.g. `test_external_fabric.py`, the
    `test_phase*.py` files) intentionally repoint the process-global
    `DATABASE_URL` / SQLAlchemy engine at their own temp SQLite file for the
    duration of their module, then call `reset_engine()` and delete that
    file on teardown — without restoring the previous state. Because pytest
    runs modules in a single process, whichever module runs next alphabetically
    (originally `test_orchestrator.py`, `test_workforce_advanced.py`,
    `test_workforce_orchestrator.py`) would silently inherit a dangling
    `DATABASE_URL` pointing at a file that no longer exists — SQLite happily
    recreates it as an empty file with no tables, reproducing the same
    "no such table" failure this conftest otherwise fixes.

    This fixture is a no-op while a module's own DB fixture is legitimately
    active (its temp file still exists on disk), and only repairs state when
    the currently configured SQLite file is missing.
    """
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("sqlite:///"):
        path = url[len("sqlite:///"):]
        if path and not os.path.exists(path):
            _pin_session_db()
    yield


try:
    import internet_fabric.models_db  # noqa: F401
except Exception:
    pass
