"""Regression: classic Orchestrator tasks and chat sessions survive restart."""

from __future__ import annotations

import os
import tempfile

import pytest

_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_DB.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_DB.name}"


@pytest.fixture(scope="module")
def db_ready():
    from database.session import reset_engine, init_db
    import config.settings as settings_mod

    os.environ["DATABASE_URL"] = f"sqlite:///{_DB.name}"
    if hasattr(settings_mod.get_settings, "cache_clear"):
        settings_mod.get_settings.cache_clear()
    reset_engine()
    init_db(f"sqlite:///{_DB.name}")
    yield
    reset_engine()
    try:
        os.unlink(_DB.name)
    except OSError:
        pass


def test_orchestrator_task_survives_restart(db_ready):
    from orchestrator.core import Orchestrator
    from schemas.tasks import TaskCreate
    from schemas.common import Priority
    from database.session import reset_engine, get_engine, get_session_factory

    orch = Orchestrator()
    task = orch.create_task(
        TaskCreate(
            request="Assess business health",
            organisation_id="org-t",
            user_id="user-t",
            priority=Priority.MEDIUM,
        )
    )
    tid = task.task_id
    orch.update_state(tid, task.state.__class__("RUNNING") if False else task.state)

    # force RUNNING
    from schemas.common import TaskState
    orch.update_state(tid, TaskState.RUNNING)

    # restart
    orch2 = Orchestrator()  # empty _tasks
    reset_engine()
    # Rebind to the same test DB URL (env DATABASE_URL)
    get_engine()
    get_session_factory()
    loaded = orch2.get_task(tid)
    assert loaded is not None
    assert loaded.organisation_id == "org-t"
    assert loaded.request == "Assess business health"
    assert loaded.state == TaskState.RUNNING


def test_chat_session_survives_restart(db_ready):
    from api.chat import ChatService, ChatMessage
    from orchestrator.core import Orchestrator
    from database.session import reset_engine, get_engine, get_session_factory

    svc = ChatService(Orchestrator())
    session = svc.create_session("org-c", "user-c", title="Health chat")
    session.messages.append(ChatMessage(role="user", content="Hello"))
    session.messages.append(ChatMessage(role="assistant", content="Hi"))
    svc._persist_session(session)
    sid = session.session_id

    # restart
    svc2 = ChatService(Orchestrator())
    reset_engine()
    # Rebind to the same test DB URL (env DATABASE_URL)
    get_engine()
    get_session_factory()
    loaded = svc2.get_session(sid, "org-c")
    assert loaded is not None
    assert loaded.title == "Health chat"
    assert len(loaded.messages) >= 2
    assert svc2.get_session(sid, "org-other") is None  # isolation


def test_header_identity_not_sufficient_in_production(db_ready):
    from core.errors import AuthenticationError
    from core.auth import resolve_identity
    from config.settings import get_settings
    from unittest.mock import patch

    with patch.object(get_settings(), "environment", "production"), patch.object(
        get_settings(), "auth_dev_fallback", False
    ):
        # Settings is lru_cached - need to clear or pass differently
        pass

    # Direct test of logic: production without ids
    from core import auth as auth_mod
    from unittest.mock import MagicMock

    settings = MagicMock()
    settings.environment = "production"
    settings.auth_dev_fallback = False
    with patch("core.auth.get_settings", return_value=settings):
        with pytest.raises(AuthenticationError):
            resolve_identity(organisation_id=None, user_id=None)
