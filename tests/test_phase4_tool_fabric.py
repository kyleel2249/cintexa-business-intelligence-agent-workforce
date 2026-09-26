"""Phase 4 Tool Fabric tests."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

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
def engine(db_ready):
    from tool_fabric.registry import ToolRegistry
    from tool_fabric.engine import ToolExecutionEngine

    reg = ToolRegistry()
    reg.bootstrap_builtins("__system__")
    eng = ToolExecutionEngine(reg)
    eng.grant_agent(
        "worker",
        [
            "READ_FILE",
            "WRITE_FILE",
            "EXECUTE_CODE",
            "EXECUTE_SHELL",
            "NETWORK_ACCESS",
            "READ_REPOSITORY",
            "BROWSER_ACCESS",
            "DEPLOY_APPLICATION",
        ],
    )
    return eng


def test_file_write_read_list(engine):
    w = engine.invoke(
        organisation_id="org1",
        tool_slug="file.write",
        input_data={"path": "notes/hello.txt", "content": "hello fabric"},
        agent_key="worker",
    )
    assert w["status"] == "COMPLETED"
    assert w["artifacts"]
    # same-execution workspace: list after write in that workspace path
    from pathlib import Path
    ws = Path(w["workspace"])
    assert (ws / "notes/hello.txt").read_text() == "hello fabric"
    listed = engine.invoke(
        organisation_id="org1",
        tool_slug="file.list",
        input_data={},
        agent_key="worker",
    )
    assert listed["status"] == "COMPLETED"


def test_path_traversal_blocked(engine):
    from core.errors import AuthorizationError, ExecutionError

    with pytest.raises((AuthorizationError, ExecutionError)):
        engine.invoke(
            organisation_id="org1",
            tool_slug="file.read",
            input_data={"path": "../../etc/passwd"},
            agent_key="worker",
        )


def test_python_success_and_error(engine):
    from core.errors import ExecutionError

    ok = engine.invoke(
        organisation_id="org1",
        tool_slug="code.python",
        input_data={"code": "print(2+2)"},
        agent_key="worker",
    )
    assert ok["status"] == "COMPLETED"
    assert "4" in ok["result"]["stdout"]

    with pytest.raises(ExecutionError):
        engine.invoke(
            organisation_id="org1",
            tool_slug="code.python",
            input_data={"code": "raise RuntimeError('boom')\n"},
            agent_key="worker",
        )


def test_python_timeout(engine):
    from core.errors import ExecutionError
    from tool_fabric.policy import ExecutionPolicy

    pol = ExecutionPolicy(organisation_id="org1", max_timeout_sec=2)
    with pytest.raises(ExecutionError):
        engine.invoke(
            organisation_id="org1",
            tool_slug="code.python",
            input_data={"code": "import time\ntime.sleep(30)"},
            agent_key="worker",
            policy=pol,
        )


def test_shell_allowlist(engine):
    from core.errors import AuthorizationError, ExecutionError

    ok = engine.invoke(
        organisation_id="org1",
        tool_slug="shell.run",
        input_data={"argv": ["echo", "safe"]},
        agent_key="worker",
    )
    assert "safe" in ok["result"]["stdout"]
    with pytest.raises((AuthorizationError, ExecutionError)):
        engine.invoke(
            organisation_id="org1",
            tool_slug="shell.run",
            input_data={"argv": ["rm", "-rf", "/"]},
            agent_key="worker",
        )


def test_http_domain_policy(engine):
    from core.errors import AuthorizationError, ExecutionError
    from tool_fabric.policy import ExecutionPolicy

    pol = ExecutionPolicy(organisation_id="org1", network_mode="deny")
    with pytest.raises((AuthorizationError, ExecutionError)):
        engine.invoke(
            organisation_id="org1",
            tool_slug="http.request",
            input_data={"url": "https://example.com/"},
            agent_key="worker",
            policy=pol,
        )


def test_permission_denied_agent(engine):
    from core.errors import AuthorizationError

    engine.grant_agent("restricted", ["READ_FILE"])
    with pytest.raises(AuthorizationError):
        engine.invoke(
            organisation_id="org1",
            tool_slug="code.python",
            input_data={"code": "print(1)"},
            agent_key="restricted",
        )


def test_approval_gate(engine):
    from persistence.unit_of_work import UnitOfWork
    from tool_fabric.models_db import TFApproval

    res = engine.invoke(
        organisation_id="org1",
        tool_slug="deploy.apply",
        input_data={"target": "prod"},
        agent_key="worker",
    )
    assert res["status"] == "PENDING_APPROVAL"
    with UnitOfWork() as uow:
        ap = uow.session.query(TFApproval).filter_by(organisation_id="org1", status="PENDING_APPROVAL").first()
        assert ap is not None
        aid = ap.approval_id
    rejected = engine.reject(aid, "org1")
    assert rejected["status"] == "REJECTED"
    # new request + approve
    res2 = engine.invoke(
        organisation_id="org1",
        tool_slug="deploy.apply",
        input_data={"target": "prod"},
        agent_key="worker",
    )
    with UnitOfWork() as uow:
        ap2 = (
            uow.session.query(TFApproval)
            .filter_by(organisation_id="org1", execution_id=res2["execution_id"])
            .one()
        )
        aid2 = ap2.approval_id
    approved = engine.approve(aid2, "org1")
    assert approved["status"] == "APPROVED"


def test_dry_run(engine):
    r = engine.invoke(
        organisation_id="org1",
        tool_slug="file.write",
        input_data={"path": "x.txt", "content": "y"},
        agent_key="worker",
        dry_run=True,
    )
    assert r["status"] == "DRY_RUN"


def test_cross_org_execution_hidden(engine):
    r = engine.invoke(
        organisation_id="org-a",
        tool_slug="code.python",
        input_data={"code": "print('a')"},
        agent_key="worker",
    )
    assert engine.get_execution(r["execution_id"], "org-a") is not None
    assert engine.get_execution(r["execution_id"], "org-b") is None


def test_restart_preserves_execution(engine, db_ready):
    r = engine.invoke(
        organisation_id="org-r",
        tool_slug="code.python",
        input_data={"code": "print('persist')"},
        agent_key="worker",
    )
    eid = r["execution_id"]
    from database.session import reset_engine, get_engine, get_session_factory
    from tool_fabric.engine import ToolExecutionEngine
    from tool_fabric.registry import ToolRegistry

    reset_engine()
    get_engine()
    get_session_factory()
    eng2 = ToolExecutionEngine(ToolRegistry())
    loaded = eng2.get_execution(eid, "org-r")
    assert loaded is not None
    assert loaded["status"] == "COMPLETED"
    assert loaded["tool_slug"] == "code.python"


def test_discovery(engine):
    from tool_fabric.registry import ToolRegistry

    reg = ToolRegistry()
    tools = reg.discover("org1", capability="execute_code")
    slugs = {t.slug for t in tools}
    assert "code.python" in slugs


def test_e2e_tool_to_knowledge(engine, db_ready):
    from knowledge_fabric.service import KnowledgeFabric

    # write analysis then ingest as knowledge
    w = engine.invoke(
        organisation_id="org-k",
        tool_slug="file.write",
        input_data={"path": "report.txt", "content": "Market grew 18% in 2025."},
        agent_key="worker",
    )
    content = "Market grew 18% in 2025."
    kf = KnowledgeFabric()
    doc = kf.ingest_document(
        organisation_id="org-k",
        content=content,
        title="tool-artifact",
        source_type="artifact",
    )
    hits = kf.search(organisation_id="org-k", query="Market grew 18%", strategy="lexical", top_k=3)
    assert hits["hits"]
    assert doc["document_id"]
