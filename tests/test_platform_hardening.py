"""Production platform hardening tests."""

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
    import agent_os.models_db  # noqa: F401
    import knowledge_fabric.models_db  # noqa: F401
    import tool_fabric.models_db  # noqa: F401
    import reliability.models_db  # noqa: F401
    import observability.models_db  # noqa: F401
    import evolution.models_db  # noqa: F401
    import cintexa_platform.models_db  # noqa: F401

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


def test_lease_fencing(db_ready):
    from cintexa_platform.leases import LeaseService
    from core.errors import AuthorizationError, ConflictError

    ls = LeaseService()
    a = ls.acquire("res-1", "worker-a", ttl_sec=60)
    with pytest.raises(ConflictError):
        ls.acquire("res-1", "worker-b", ttl_sec=60)
    ls.renew("res-1", "worker-a", a["fencing_token"], ttl_sec=60)
    with pytest.raises(AuthorizationError):
        ls.renew("res-1", "worker-a", a["fencing_token"] + 99, ttl_sec=60)
    ls.release("res-1", "worker-a", a["fencing_token"])
    b = ls.acquire("res-1", "worker-b", ttl_sec=60)
    assert b["owner"] == "worker-b"


def test_job_claim_complete_dead(db_ready):
    from cintexa_platform.workers import JobQueue, WorkerRegistry

    WorkerRegistry().register("w1", hostname="h1")
    q = JobQueue()
    j = q.enqueue("test.op", {"x": 1}, organisation_id="org1", idempotency_key="idem-1")
    j2 = q.enqueue("test.op", {"x": 1}, organisation_id="org1", idempotency_key="idem-1")
    assert j2["deduped"] is True
    claimed = q.claim("w1")
    assert claimed and claimed["job_id"] == j["job_id"]
    q.complete(claimed["job_id"], "w1", {"ok": True})


def test_durable_circuit_multi_view(db_ready):
    from cintexa_platform.coordination import DurableCircuit

    c1 = DurableCircuit("prov-x", failure_threshold=2, cooldown_sec=0.01)
    c2 = DurableCircuit("prov-x", failure_threshold=2, cooldown_sec=0.01)
    assert c1.allow()
    c1.record_failure()
    c1.record_failure()
    assert c2.status()["state"] == "OPEN"
    assert c2.allow() is False


def test_canary_weighted_sticky(db_ready):
    from cintexa_platform.canary import CanaryRouter

    r = CanaryRouter()
    r.upsert_route(
        "orgC",
        "agent:research",
        baseline_version="v1",
        candidate_version="v2",
        percent=100,
    )
    ch = r.choose("orgC", "agent:research", subject_key="user-1")
    assert ch["bucket"] == "candidate"
    r.upsert_route("orgC", "agent:research", baseline_version="v1", candidate_version="v2", percent=0)
    ch2 = r.choose("orgC", "agent:research", subject_key="user-1")
    assert ch2["bucket"] == "baseline"
    # sticky consistency at 50%
    r.upsert_route("orgC", "agent:research", baseline_version="v1", candidate_version="v2", percent=50)
    a = r.choose("orgC", "agent:research", subject_key="sticky-user")
    b = r.choose("orgC", "agent:research", subject_key="sticky-user")
    assert a["bucket"] == b["bucket"]


def test_vault_server_not_client(db_ready):
    from cintexa_platform.vault import SecretVault

    v = SecretVault()
    v.put("openrouter_api_key", "sk-or-v1-secretvalue", organisation_id="org1")
    assert v.get_for_server("openrouter_api_key", "org1").startswith("sk-or")
    red = v.redact_for_client({"api_key": "sk-or-v1-secretvalue", "ok": 1})
    assert red["api_key"] == "[REDACTED]"


def test_prod_settings_reject_sqlite():
    from config.settings import Settings, validate_production_settings

    s = Settings(
        environment="production",
        secret_key="a" * 40,
        auth_dev_fallback=False,
        database_url="sqlite:///./x.db",
    )
    with pytest.raises(RuntimeError):
        validate_production_settings(s)


def test_durable_freeze(db_ready):
    from cintexa_platform.coordination import DurableFreeze

    df = DurableFreeze()
    df.clear_emergency(authorized=True)
    df.freeze("incident")
    assert df.status()["frozen"] is True
    df.unfreeze()
    df.emergency("x")
    assert df.status()["emergency_stop"] is True
    df.clear_emergency(authorized=True)


def test_idempotency_store(db_ready):
    from cintexa_platform.idempotency import IdempotencyStore

    s = IdempotencyStore()
    assert s.get("k1", "org1") is None
    s.put("k1", {"status": 200, "body": {"id": "1"}}, organisation_id="org1")
    assert s.get("k1", "org1")["body"]["id"] == "1"


def test_concurrent_claim_no_duplicates(db_ready):
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from cintexa_platform.workers import JobQueue, WorkerRegistry

    for i in range(4):
        WorkerRegistry().register(f"cw{i}")
    q = JobQueue()
    for i in range(12):
        q.enqueue("c.op", {"i": i}, organisation_id="orgC")
    claimed = []

    def worker(wid):
        got = []
        while True:
            j = q.claim(wid)
            if not j:
                break
            got.append(j["job_id"])
            q.complete(j["job_id"], wid, {})
        return got

    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(worker, f"cw{i}") for i in range(4)]
        for f in as_completed(futs):
            claimed.extend(f.result())
    assert len(claimed) == 12
    assert len(set(claimed)) == 12


def test_stale_owner_cannot_complete(db_ready):
    from datetime import datetime, timedelta
    from cintexa_platform.workers import JobQueue, WorkerRegistry
    from cintexa_platform.models_db import PlatformJob
    from persistence.unit_of_work import UnitOfWork
    from core.errors import ConflictError

    WorkerRegistry().register("sa")
    WorkerRegistry().register("sb")
    q = JobQueue()
    j = q.enqueue("stale", {"x": 1}, organisation_id="orgS")
    c1 = q.claim("sa", visibility_timeout_sec=1)
    with UnitOfWork() as uow:
        row = uow.session.get(PlatformJob, c1["job_id"])
        row.lease_expires_at = datetime.utcnow() - timedelta(seconds=5)
    c2 = q.claim("sb")
    assert c2["job_id"] == c1["job_id"]
    with pytest.raises(ConflictError):
        q.complete(c1["job_id"], "sa", {})
    q.complete(c2["job_id"], "sb", {"ok": True})
