"""Phase 2 Agent Operating System — registry, lifecycle, graph, handoff, isolation."""

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


@pytest.fixture
def reg(db_ready):
    from agent_os.registry import AgentOSRegistry
    return AgentOSRegistry()


@pytest.fixture
def runtime(reg):
    from agent_os.runtime import AgentRuntime
    return AgentRuntime(reg)


def test_register_retrieve_lifecycle(reg):
    from agent_os.lifecycle import AgentLifecycleState

    a = reg.register(
        organisation_id="org1",
        agent_key="research",
        name="Research Agent",
        capabilities=["research", "web_search"],
        version="1.0.0",
    )
    assert a.lifecycle_state == "REGISTERED"
    got = reg.get(a.id, "org1")
    assert got is not None
    assert got.agent_key == "research"
    assert reg.get(a.id, "org-other") is None

    reg.activate(a.id, "org1")
    assert reg.get(a.id, "org1").lifecycle_state == "ACTIVE"
    reg.pause(a.id, "org1")
    assert reg.get(a.id, "org1").lifecycle_state == "PAUSED"
    reg.activate(a.id, "org1")
    reg.drain(a.id, "org1")
    assert reg.get(a.id, "org1").lifecycle_state == "DRAINING"
    reg.disable(a.id, "org1")
    assert reg.get(a.id, "org1").lifecycle_state == "DISABLED"


def test_invalid_lifecycle_transition(reg):
    from core.errors import ConflictError
    from agent_os.lifecycle import AgentLifecycleState

    a = reg.register(
        organisation_id="org1",
        agent_key="x_agent",
        name="X",
        capabilities=["x"],
        version="1.0.0",
    )
    # REGISTERED → PAUSED not allowed
    with pytest.raises(ConflictError):
        reg.set_lifecycle(a.id, "org1", AgentLifecycleState.PAUSED)


def test_capability_discovery(reg):
    a = reg.register(organisation_id="org2", agent_key="ra", name="A", capabilities=["research"], version="1.0.0")
    b = reg.register(organisation_id="org2", agent_key="rb", name="B", capabilities=["research"], version="1.0.0")
    c = reg.register(organisation_id="org2", agent_key="fc", name="C", capabilities=["financial_analysis"], version="1.0.0")
    reg.activate(a.id, "org2")
    reg.activate(b.id, "org2")
    reg.activate(c.id, "org2")

    research = reg.find_by_capability("org2", "research")
    keys = {x.agent_key for x in research}
    assert keys == {"ra", "rb"}
    fin = reg.find_by_capability("org2", "financial_analysis")
    assert {x.agent_key for x in fin} == {"fc"}

    reg.disable(a.id, "org2")
    research2 = reg.find_by_capability("org2", "research")
    assert {x.agent_key for x in research2} == {"rb"}


def test_selection_skips_disabled(reg, runtime):
    from core.errors import NotFoundError

    a = reg.register(organisation_id="org3", agent_key="only", name="Only", capabilities=["cap_only"], version="1.0.0")
    reg.activate(a.id, "org3")
    reg.disable(a.id, "org3")
    with pytest.raises(NotFoundError):
        runtime.assign(organisation_id="org3", capability="cap_only")


def test_contract_validation(runtime, reg):
    from core.errors import ValidationError

    a = reg.register(
        organisation_id="org4",
        agent_key="research",
        name="Research",
        capabilities=["research"],
        version="1.0.0",
    )
    reg.activate(a.id, "org4")
    with pytest.raises(ValidationError):
        runtime.execute(
            organisation_id="org4",
            agent_id=a.id,
            input_data={},  # missing query
            capability="research",
        )
    result = runtime.execute(
        organisation_id="org4",
        agent_id=a.id,
        input_data={"query": "market size"},
        capability="research",
        task_id="t-contract-1",
    )
    assert result["status"] == "COMPLETED"
    assert "findings" in result["output"]


def test_workflow_graph_diamond(runtime, reg):
    """A → B, A → C, B+C → D"""
    for key, caps in [("ga", ["g_start"]), ("gb", ["g_mid"]), ("gc", ["g_mid"]), ("gd", ["g_end"])]:
        ag = reg.register(organisation_id="org5", agent_key=key, name=key, capabilities=caps, version="1.0.0")
        reg.activate(ag.id, "org5")

    from persistence.unit_of_work import UnitOfWork

    with UnitOfWork() as uow:
        uow.workflows.create(
            workflow_id="wf-diamond",
            organisation_id="org5",
            user_id="u1",
            objective="diamond graph",
            status="RUNNING",
        )

    runtime.create_graph(
        organisation_id="org5",
        workflow_id="wf-diamond",
        nodes=[
            {"name": "A", "capability": "g_start", "input_data": {"query": "start"}},
            {"name": "B", "capability": "g_mid", "depends_on": ["A"], "input_data": {"query": "b"}},
            {"name": "C", "capability": "g_mid", "depends_on": ["A"], "input_data": {"query": "c"}},
            {"name": "D", "capability": "g_end", "depends_on": ["B", "C"], "input_data": {"query": "d"}},
        ],
    )
    result = runtime.run_graph(organisation_id="org5", workflow_id="wf-diamond")
    assert result["nodes"]["A"] == "COMPLETED"
    assert result["nodes"]["B"] == "COMPLETED"
    assert result["nodes"]["C"] == "COMPLETED"
    assert result["nodes"]["D"] == "COMPLETED"
    assert "upstream" in str(result["outputs"].get("D", {})) or result["outputs"].get("D")


def test_handoff_and_messages(runtime, reg):
    msg = runtime.handoff(
        organisation_id="org6",
        sender="research",
        recipient="analysis",
        payload={"findings": [1, 2, 3]},
        task_id="t1",
        correlation_id="corr-h1",
    )
    assert msg["message_type"] == "HANDOFF"
    from persistence.unit_of_work import UnitOfWork
    from agent_os.models_db import AgentMessageRecordOS

    with UnitOfWork() as uow:
        rows = (
            uow.session.query(AgentMessageRecordOS)
            .filter_by(organisation_id="org6", message_type="HANDOFF")
            .all()
        )
        assert len(rows) >= 1
        assert rows[0].correlation_id == "corr-h1"
        # isolation
        assert (
            uow.session.query(AgentMessageRecordOS)
            .filter_by(organisation_id="org-other", message_id=rows[0].message_id)
            .count()
            == 0
        )


def test_versioning_preserves_history(runtime, reg):
    a1 = reg.register(
        organisation_id="org7",
        agent_key="research",
        name="R1",
        capabilities=["research"],
        version="1.0.0",
        make_active=True,
    )
    reg.activate(a1.id, "org7")
    r1 = runtime.execute(
        organisation_id="org7",
        agent_id=a1.id,
        input_data={"query": "v1"},
        capability="research",
        task_id="tv1",
    )
    assert r1["agent_version"] == "1.0.0"

    a2 = reg.register(
        organisation_id="org7",
        agent_key="research",
        name="R2",
        capabilities=["research"],
        version="2.0.0",
        make_active=True,
    )
    reg.activate(a2.id, "org7")
    active = reg.get_by_key("org7", "research")
    assert active.version == "2.0.0"
    r2 = runtime.execute(
        organisation_id="org7",
        agent_id=a2.id,
        input_data={"query": "v2"},
        capability="research",
        task_id="tv2",
    )
    assert r2["agent_version"] == "2.0.0"

    # historical execution still v1
    from persistence.unit_of_work import UnitOfWork
    from agent_os.models_db import AgentExecutionRecord

    with UnitOfWork() as uow:
        e1 = uow.session.get(AgentExecutionRecord, r1["execution_id"])
        assert e1.agent_version == "1.0.0"


def test_draining_blocks_new_assignment(reg, runtime):
    from core.errors import NotFoundError, ConflictError

    a = reg.register(
        organisation_id="org8",
        agent_key="drainme",
        name="Drain",
        capabilities=["drain_cap"],
        version="1.0.0",
    )
    reg.activate(a.id, "org8")
    reg.drain(a.id, "org8")
    # select_agent only_accepting_work skips DRAINING
    assert reg.select_agent("org8", "drain_cap") is None
    with pytest.raises(NotFoundError):
        runtime.assign(organisation_id="org8", capability="drain_cap")


def test_clarification_and_escalation(runtime, reg, db_ready):
    from persistence.unit_of_work import UnitOfWork

    with UnitOfWork() as uow:
        uow.workflows.create(
            workflow_id="wf-wait",
            organisation_id="org9",
            user_id="u",
            objective="need data",
            status="RUNNING",
        )
    clar = runtime.request_clarification(
        organisation_id="org9",
        agent_key="research",
        missing_fields=["time_range", "region"],
        workflow_id="wf-wait",
    )
    assert clar["workflow_status"] == "WAITING"
    esc = runtime.escalate(
        organisation_id="org9",
        reason="Need human approval for external publish",
        agent_key="research",
        workflow_id="wf-wait",
    )
    assert esc["status"] == "OPEN"
    loaded = runtime.get_escalation(esc["escalation_id"], "org9")
    assert loaded is not None
    assert runtime.get_escalation(esc["escalation_id"], "org-other") is None


def test_idempotent_execution(runtime, reg):
    a = reg.register(
        organisation_id="org10",
        agent_key="idem",
        name="Idem",
        capabilities=["research"],
        version="1.0.0",
    )
    reg.activate(a.id, "org10")
    r1 = runtime.execute(
        organisation_id="org10",
        agent_id=a.id,
        input_data={"query": "q"},
        capability="research",
        task_id="same-task",
    )
    r2 = runtime.execute(
        organisation_id="org10",
        agent_id=a.id,
        input_data={"query": "q"},
        capability="research",
        task_id="same-task",
    )
    assert r2.get("idempotent") is True
    assert r2["execution_id"] == r1["execution_id"]


def test_failure_persisted(runtime, reg):
    from core.errors import ExecutionError

    a = reg.register(
        organisation_id="org11",
        agent_key="failbot",
        name="Fail",
        capabilities=["research"],
        version="1.0.0",
    )
    reg.activate(a.id, "org11")

    def boom(data):
        raise RuntimeError("intentional failure")

    runtime.register_handler("failbot", boom)
    with pytest.raises(ExecutionError):
        runtime.execute(
            organisation_id="org11",
            agent_id=a.id,
            input_data={"query": "x"},
            capability="research",
            task_id="fail-1",
            output_schema=None,
            input_schema={"required": ["query"]},
        )
    from persistence.unit_of_work import UnitOfWork
    from agent_os.models_db import AgentExecutionRecord

    with UnitOfWork() as uow:
        fails = (
            uow.session.query(AgentExecutionRecord)
            .filter_by(organisation_id="org11", status="FAILED")
            .all()
        )
        assert len(fails) >= 1
        assert "intentional" in (fails[0].error or "")


def test_restart_preserves_registry(reg, db_ready):
    a = reg.register(
        organisation_id="org12",
        agent_key="persist",
        name="Persist",
        capabilities=["research"],
        version="1.0.0",
    )
    reg.activate(a.id, "org12")
    aid = a.id

    from database.session import reset_engine, get_engine, get_session_factory
    from agent_os.registry import AgentOSRegistry

    reset_engine()
    get_engine()
    get_session_factory()
    reg2 = AgentOSRegistry()
    loaded = reg2.get(aid, "org12")
    assert loaded is not None
    assert loaded.lifecycle_state == "ACTIVE"
    assert loaded.agent_key == "persist"
