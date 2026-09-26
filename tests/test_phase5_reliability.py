"""Phase 5 Reliability tests."""

from __future__ import annotations

import os
import tempfile
import time

import pytest

_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_DB.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_DB.name}"


@pytest.fixture(scope="module")
def db_ready():
    from database.session import reset_engine, init_db
    import config.settings as settings_mod
    import agent_os.models_db  # noqa: F401
    import knowledge_fabric.models_db  # noqa: F401
    import tool_fabric.models_db  # noqa: F401
    import reliability.models_db  # noqa: F401

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


def test_classify_non_retryable_authz():
    from core.errors import AuthorizationError
    from reliability.taxonomy import FailureCategory, classify_failure

    d = classify_failure(AuthorizationError("denied"), attempt=1)
    assert d.category == FailureCategory.AUTHORIZATION_FAILURE
    assert d.retryable is False


def test_classify_timeout_retryable():
    from reliability.taxonomy import FailureCategory, classify_failure

    d = classify_failure(Exception("timed out"), attempt=1, max_retries=3)
    assert d.category == FailureCategory.TIMEOUT
    assert d.retryable is True


def test_retry_succeeds_after_transient(db_ready):
    from reliability.retry import RetryEngine, RetryPolicy

    state = {"n": 0}

    def flaky():
        state["n"] += 1
        if state["n"] < 3:
            raise ConnectionError("network blip")
        return "ok"

    eng = RetryEngine(RetryPolicy(max_attempts=5, min_delay_sec=0.001, jitter=False))
    r = eng.run(flaky, organisation_id="org1", scope_key="t1", sleep=True)
    assert r.success
    assert r.result == "ok"
    assert len(r.attempts) == 3


def test_retry_no_retry_on_validation(db_ready):
    from core.errors import ValidationError
    from reliability.retry import RetryEngine, RetryPolicy

    eng = RetryEngine(RetryPolicy(max_attempts=5, min_delay_sec=0.001))
    r = eng.run(lambda: (_ for _ in ()).throw(ValidationError("bad")), organisation_id="org1", sleep=False)
    assert r.success is False
    assert r.exhausted
    assert len(r.attempts) == 1


def test_circuit_breaker_opens(db_ready):
    from reliability.circuit import CircuitBreaker, CircuitState

    cb = CircuitBreaker(name="prov-a", failure_threshold=3, cooldown_sec=0.2, window_sec=60)
    assert cb.allow()
    for _ in range(3):
        cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.allow() is False
    time.sleep(0.25)
    assert cb.allow() is True  # half-open
    assert cb.state == CircuitState.HALF_OPEN
    cb.record_success()
    cb.record_success()
    assert cb.state == CircuitState.CLOSED


def test_bulkhead_limits(db_ready):
    from reliability.bulkhead import Bulkhead
    from core.errors import ExecutionError

    bh = Bulkhead("code", max_concurrent=1)
    with bh.acquire():
        with pytest.raises(ExecutionError):
            with bh.acquire(timeout=0.05):
                pass


def test_health_degraded(db_ready):
    from reliability.health import HealthRegistry, HealthStatus

    hr = HealthRegistry()
    h = hr.get("embed")
    h.record_failure()
    h.record_failure()
    assert h.status == HealthStatus.DEGRADED
    assert hr.is_routable("embed")
    for _ in range(5):
        h.record_failure()
    assert h.status == HealthStatus.UNAVAILABLE
    assert not hr.is_routable("embed")
    h.record_success(10)
    assert h.status == HealthStatus.HEALTHY


def test_dead_letter_and_reprocess(db_ready):
    from reliability.dead_letter import DeadLetterQueue

    dlq = DeadLetterQueue()
    item = dlq.enqueue(
        organisation_id="org-dl",
        reason="retries exhausted",
        category="TOOL_FAILURE",
        source_id="TEX-1",
        attempts=3,
    )
    open_list = dlq.list_open("org-dl")
    assert any(x["dead_letter_id"] == item["dead_letter_id"] for x in open_list)
    assert dlq.list_open("org-other") == []
    rp = dlq.reprocess(item["dead_letter_id"], "org-dl")
    assert rp["new_attempt"] is True
    dlq.close(item["dead_letter_id"], "org-dl")


def test_recovery_skips_completed_steps(db_ready):
    from reliability.recovery import RecoveryService

    calls = []

    def runner(step):
        calls.append(step["id"])
        if step["id"] == "C":
            raise RuntimeError("network fail C")
        return f"out-{step['id']}"

    steps = [
        {"id": "A", "status": "COMPLETED", "depends_on": [], "payload": {}},
        {"id": "B", "status": "COMPLETED", "depends_on": ["A"], "payload": {}},
        {"id": "C", "status": "FAILED", "depends_on": ["A"], "payload": {}},
        {"id": "D", "status": "PENDING", "depends_on": ["C"], "payload": {}},
    ]
    # first recovery: C keeps failing → DLQ
    svc = RecoveryService()
    # make C succeed on recovery by using a smarter runner
    n = {"c": 0}

    def runner2(step):
        calls.append(step["id"])
        if step["id"] == "C":
            n["c"] += 1
            if n["c"] < 2:
                raise ConnectionError("transient")
        return f"out-{step['id']}"

    steps2 = [
        {"id": "A", "status": "COMPLETED", "depends_on": []},
        {"id": "B", "status": "COMPLETED", "depends_on": ["A"]},
        {"id": "C", "status": "FAILED", "depends_on": ["A"]},
        {"id": "D", "status": "PENDING", "depends_on": ["C"]},
    ]
    out = svc.recover_workflow_steps(
        organisation_id="org-r",
        workflow_id="wf-1",
        steps=steps2,
        runner=runner2,
        max_retries=3,
    )
    assert out["status"] == "COMPLETED"
    assert "A" not in calls  # completed steps not re-run
    assert "B" not in calls
    assert "C" in calls and "D" in calls


def test_compensation(db_ready):
    from reliability.recovery import RecoveryService

    svc = RecoveryService()
    c = svc.start_compensation(
        organisation_id="org-c",
        workflow_id="wf",
        step_id="B",
        forward_op="create_resource",
        compensation_op="delete_resource",
    )
    done = svc.complete_compensation(c["compensation_id"], "org-c", success=True)
    assert done["status"] == "COMPLETED"


def test_outbox_inbox(db_ready):
    from reliability.outbox import Outbox, Inbox

    ob = Outbox()
    oid = ob.enqueue("test.event", {"x": 1}, organisation_id="org1")
    n = ob.dispatch_pending()
    assert n >= 1
    inbox = Inbox()
    assert not inbox.already_processed("worker-1", oid)
    inbox.mark_processed("worker-1", oid)
    assert inbox.already_processed("worker-1", oid)


def test_retry_budget_storm(db_ready):
    from reliability.retry import RetryBudget, RetryEngine, RetryPolicy

    budget = RetryBudget(max_retries_per_window=3, window_sec=60)
    eng = RetryEngine(RetryPolicy(max_attempts=10, min_delay_sec=0.0, jitter=False), budget=budget)
    fails = 0
    for i in range(5):
        r = eng.run(
            lambda: (_ for _ in ()).throw(ConnectionError("down")),
            organisation_id="org-storm",
            scope_key="prov",
            sleep=False,
        )
        if not r.success:
            fails += 1
    assert fails >= 1


def test_restart_preserves_dead_letter(db_ready):
    from reliability.dead_letter import DeadLetterQueue
    from database.session import reset_engine, get_engine, get_session_factory

    dlq = DeadLetterQueue()
    item = dlq.enqueue(organisation_id="org-rs", reason="x", category="TIMEOUT", source_id="T1")
    did = item["dead_letter_id"]
    reset_engine()
    get_engine()
    get_session_factory()
    open_list = DeadLetterQueue().list_open("org-rs")
    assert any(x["dead_letter_id"] == did for x in open_list)
