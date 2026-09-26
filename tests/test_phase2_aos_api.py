"""Phase 2 Agent OS HTTP API tests."""

from __future__ import annotations

import os
import tempfile

import pytest

_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_DB.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_DB.name}"


@pytest.fixture(scope="module")
def client():
    from database.session import reset_engine, init_db
    import config.settings as settings_mod
    import agent_os.models_db  # noqa: F401

    os.environ["DATABASE_URL"] = f"sqlite:///{_DB.name}"
    if hasattr(settings_mod.get_settings, "cache_clear"):
        settings_mod.get_settings.cache_clear()
    reset_engine()
    init_db(f"sqlite:///{_DB.name}")

    from fastapi.testclient import TestClient
    from api.main import app

    with TestClient(app) as c:
        yield c
    reset_engine()
    try:
        os.unlink(_DB.name)
    except OSError:
        pass


def _h(org="org-api", user="u1"):
    return {"X-Organisation-Id": org, "X-User-Id": user}


def test_aos_register_list_lifecycle_api(client):
    r = client.post(
        "/bi/aos/agents",
        json={"agent_key": "research", "name": "Research", "capabilities": ["research"], "version": "1.0.0"},
        headers=_h(),
    )
    assert r.status_code == 200, r.text
    agent_id = r.json()["id"]

    listed = client.get("/bi/aos/agents", headers=_h())
    assert listed.status_code == 200
    assert any(a["id"] == agent_id for a in listed.json()["agents"])

    # cross-tenant get 404
    cross = client.get(f"/bi/aos/agents/{agent_id}", headers=_h("org-other"))
    assert cross.status_code == 404

    act = client.post(f"/bi/aos/agents/{agent_id}/activate", headers=_h())
    assert act.status_code == 200
    assert act.json()["lifecycle_state"] == "ACTIVE"

    caps = client.get("/bi/aos/capabilities/research", headers=_h())
    assert caps.status_code == 200
    assert any(a["id"] == agent_id for a in caps.json()["agents"])

    exe = client.post(
        "/bi/aos/execute",
        json={"agent_id": agent_id, "input_data": {"query": "markets"}, "capability": "research", "task_id": "t-api-1"},
        headers=_h(),
    )
    assert exe.status_code == 200
    assert exe.json()["status"] == "COMPLETED"

    # invalid input
    bad = client.post(
        "/bi/aos/execute",
        json={"agent_id": agent_id, "input_data": {}, "capability": "research"},
        headers=_h(),
    )
    assert bad.status_code == 400

    client.post(f"/bi/aos/agents/{agent_id}/drain", headers=_h())
    client.post(f"/bi/aos/agents/{agent_id}/disable", headers=_h())
    got = client.get(f"/bi/aos/agents/{agent_id}", headers=_h())
    assert got.json()["lifecycle_state"] == "DISABLED"


def test_aos_duplicate_register(client):
    body = {"agent_key": "dup", "name": "Dup", "capabilities": ["x"], "version": "1.0.0"}
    assert client.post("/bi/aos/agents", json=body, headers=_h("org-dup")).status_code == 200
    assert client.post("/bi/aos/agents", json=body, headers=_h("org-dup")).status_code == 400
