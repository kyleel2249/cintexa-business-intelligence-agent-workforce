"""Phase 1 durable foundation tests — restart recovery & multi-tenant isolation."""

from __future__ import annotations

import os
import tempfile

import pytest

# Use isolated SQLite file
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


def test_org_user_membership(db_ready):
    from persistence.unit_of_work import UnitOfWork
    from core.auth import ensure_org_user

    with UnitOfWork() as uow:
        org, user, memb = ensure_org_user(uow.session, "org-a", "user-a", email="a@test.com")
        assert org.id == "org-a"
        assert user.id == "user-a"
        assert memb.organisation_id == "org-a"
        assert uow.users.is_member("org-a", "user-a")


def test_task_persist_and_retrieve(db_ready):
    from persistence.unit_of_work import UnitOfWork

    with UnitOfWork() as uow:
        uow.organisations.get_or_create("org-a", "Org A")
        task = uow.tasks.create(
            organisation_id="org-a",
            user_id="user-a",
            request="Analyse revenue",
            objective="revenue_analysis",
            state="PENDING",
        )
        tid = task.task_id
    with UnitOfWork() as uow:
        loaded = uow.tasks.get(tid, "org-a")
        assert loaded is not None
        assert loaded.request == "Analyse revenue"
        # Org isolation
        assert uow.tasks.get(tid, "org-b") is None


def test_workflow_checkpoint_recovery(db_ready):
    from persistence.unit_of_work import UnitOfWork

    with UnitOfWork() as uow:
        uow.organisations.get_or_create("org-a", "Org A")
        wf = uow.workflows.create(
            organisation_id="org-a",
            user_id="user-a",
            objective="Diagnose sales decline",
            status="RUNNING",
            current_state="step_3",
        )
        wid = wf.workflow_id
        uow.workflows.add_step(
            workflow_id=wid,
            organisation_id="org-a",
            sequence=1,
            objective="Sales analysis",
            status="COMPLETED",
        )
        uow.workflows.add_step(
            workflow_id=wid,
            organisation_id="org-a",
            sequence=2,
            objective="Customer analysis",
            status="COMPLETED",
        )
        uow.workflows.add_step(
            workflow_id=wid,
            organisation_id="org-a",
            sequence=3,
            objective="Recovery plan",
            status="PENDING",
        )
        cp = uow.checkpoints.create(
            workflow_id=wid,
            organisation_id="org-a",
            current_step="step_3",
            completed_steps=["1", "2"],
            pending_steps=["3"],
            version=1,
        )
        assert cp.checkpoint_id

    # Simulate restart
    from database.session import reset_engine, get_engine, get_session_factory

    reset_engine()
    # Rebind to the same test DB URL (env DATABASE_URL)
    get_engine()
    get_session_factory()

    with UnitOfWork() as uow:
        wf = uow.workflows.get(wid, "org-a")
        assert wf is not None
        assert wf.status == "RUNNING"
        steps = uow.workflows.list_steps(wid, "org-a")
        assert len(steps) == 3
        completed = [s for s in steps if s.status == "COMPLETED"]
        pending = [s for s in steps if s.status == "PENDING"]
        assert len(completed) == 2
        assert len(pending) == 1
        latest = uow.checkpoints.latest(wid, "org-a")
        assert latest is not None
        assert "3" in latest.pending_steps


def test_events_durable(db_ready):
    from events.bus import bus
    from database.session import reset_engine, get_engine, get_session_factory

    bus.publish(
        "mission.created",
        {"mission_id": "m1", "objective": "test"},
        organisation_id="org-a",
        correlation_id="corr-1",
    )
    hist = bus.history(organisation_id="org-a", limit=10)
    assert any(e["event_type"] == "mission.created" for e in hist)

    reset_engine()
    # Rebind to the same test DB URL (env DATABASE_URL)
    get_engine()
    get_session_factory()
    hist2 = bus.history(organisation_id="org-a", limit=10)
    assert any(e["event_type"] == "mission.created" for e in hist2)


def test_memory_isolation(db_ready):
    from persistence.unit_of_work import UnitOfWork

    with UnitOfWork() as uow:
        uow.memories.create(organisation_id="org-a", content={"note": "secret-a"}, memory_type="working")
        uow.memories.create(organisation_id="org-b", content={"note": "secret-b"}, memory_type="working")
    with UnitOfWork() as uow:
        a = uow.memories.list_for_org("org-a")
        b = uow.memories.list_for_org("org-b")
        assert all("secret-a" in str(i.content) for i in a)
        assert all("secret-b" not in str(i.content) for i in a)
        assert all("secret-b" in str(i.content) for i in b)


def test_mission_restart_recovery(db_ready):
    from schemas.missions import Mission, MissionStatus, MissionTask, MissionTaskStatus
    from orchestrator.mission_manager import MissionManager
    from database.session import reset_engine, get_engine, get_session_factory

    mgr = MissionManager()
    mission = Mission(
        organisation_id="org-recover",
        user_id="user-r",
        objective="Diagnose revenue decline",
        original_request="Why did revenue drop?",
        status=MissionStatus.RUNNING,
        plan_version=1,
        tasks=[
            MissionTask(objective="Trend analysis", status=MissionTaskStatus.COMPLETED),
            MissionTask(objective="Driver analysis", status=MissionTaskStatus.PENDING),
        ],
        idempotency_key="idem-recover-1",
    )
    # mark first task id for checkpoint
    mission.tasks[0].status = MissionTaskStatus.COMPLETED
    mgr.save(mission)
    mid = mission.mission_id

    # Process "dies"
    mgr.clear_cache()
    reset_engine()
    # Rebind to the same test DB URL (env DATABASE_URL)
    get_engine()
    get_session_factory()

    mgr2 = MissionManager()
    loaded = mgr2.get_for_org(mid, "org-recover")
    assert loaded is not None
    assert loaded.objective == "Diagnose revenue decline"
    assert loaded.status == MissionStatus.RUNNING
    assert any(t.status == MissionTaskStatus.COMPLETED for t in loaded.tasks)
    # Idempotency
    again = mgr2.get_by_idempotency("org-recover", "idem-recover-1")
    assert again is not None
    assert again.mission_id == mid


def test_idempotent_workflow_create(db_ready):
    from persistence.unit_of_work import UnitOfWork

    with UnitOfWork() as uow:
        uow.organisations.get_or_create("org-a", "Org A")
        w1 = uow.workflows.create(
            organisation_id="org-a",
            user_id="u1",
            objective="x",
            idempotency_key="key-1",
        )
        existing = uow.workflows.get_by_idempotency("org-a", "key-1")
        assert existing is not None
        assert existing.workflow_id == w1.workflow_id


def test_optimistic_concurrency(db_ready):
    from persistence.unit_of_work import UnitOfWork
    from core.errors import ConflictError

    with UnitOfWork() as uow:
        uow.organisations.get_or_create("org-a", "Org A")
        wf = uow.workflows.create(organisation_id="org-a", user_id="u1", objective="x", status="RUNNING")
        wid = wf.workflow_id
        ver = wf.version
    with UnitOfWork() as uow:
        uow.workflows.update(wid, "org-a", expected_version=ver, status="COMPLETED")
    with UnitOfWork() as uow:
        with pytest.raises(ConflictError):
            uow.workflows.update(wid, "org-a", expected_version=ver, status="FAILED")


def test_audit_no_secrets(db_ready):
    from persistence.unit_of_work import UnitOfWork
    from core.logging import scrub

    assert "REDACTED" in scrub("api_key=sk-abc123secret")
    assert "REDACTED" in scrub("Bearer tokensecretvalue")
    with UnitOfWork() as uow:
        uow.audits.record(
            organisation_id="org-a",
            actor="user-a",
            action="task.complete",
            resource_type="task",
            resource_id="t1",
            details={"status": "COMPLETED"},
        )
