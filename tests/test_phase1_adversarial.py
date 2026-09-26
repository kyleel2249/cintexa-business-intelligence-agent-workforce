"""Adversarial multi-tenant and transaction tests for Phase 1."""

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


def test_cross_org_task_read_denied(db_ready):
    from persistence.unit_of_work import UnitOfWork

    with UnitOfWork() as uow:
        uow.organisations.get_or_create("org-a")
        uow.organisations.get_or_create("org-b")
        t = uow.tasks.create(organisation_id="org-a", user_id="ua", request="secret", objective="x")
        tid = t.task_id
    with UnitOfWork() as uow:
        assert uow.tasks.get(tid, "org-a") is not None
        assert uow.tasks.get(tid, "org-b") is None


def test_cross_org_mission_denied(db_ready):
    from schemas.missions import Mission, MissionStatus
    from orchestrator.mission_manager import MissionManager

    mgr = MissionManager()
    m = Mission(organisation_id="org-a", user_id="ua", objective="A-only", status=MissionStatus.COMPLETED)
    mgr.save(m)
    assert mgr.get_for_org(m.mission_id, "org-a") is not None
    assert mgr.get_for_org(m.mission_id, "org-b") is None


def test_cross_org_conversation_denied(db_ready):
    from api.chat import ChatService, ChatMessage
    from orchestrator.core import Orchestrator

    svc = ChatService(Orchestrator())
    s = svc.create_session("org-a", "ua", title="private")
    s.messages.append(ChatMessage(role="user", content="secret"))
    svc._persist_session(s)
    assert svc.get_session(s.session_id, "org-a") is not None
    assert svc.get_session(s.session_id, "org-b") is None


def test_transaction_rollback_on_error(db_ready):
    from persistence.unit_of_work import UnitOfWork

    with pytest.raises(RuntimeError):
        with UnitOfWork() as uow:
            uow.organisations.get_or_create("org-roll")
            uow.tasks.create(organisation_id="org-roll", user_id="u", request="x", objective="y")
            raise RuntimeError("force fail")
    with UnitOfWork() as uow:
        # org may or may not exist depending on flush order — tasks must not remain
        tasks = uow.tasks.list_for_org("org-roll")
        assert tasks == []


def test_fresh_migration_schema(db_ready):
    from database.session import get_engine
    from sqlalchemy import inspect

    insp = inspect(get_engine())
    tables = set(insp.get_table_names())
    required = {
        "organisations", "users", "memberships", "agent_tasks", "workflows",
        "workflow_steps", "checkpoints", "missions", "durable_events",
        "memories", "conversations", "audit_logs",
    }
    missing = required - tables
    assert not missing, f"Missing tables: {missing}"
