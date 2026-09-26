"""HTTP-level regression tests for the FastAPI app — covers the QA gate wiring
and the /bi/reports endpoint (added to expose the previously-unwired
reports.generator module)."""

import json

import pytest
from fastapi.testclient import TestClient

from api.main import app

HEADERS = {"X-Organisation-Id": "default-org", "X-User-Id": "default-user"}


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert len(res.json()["agents"]) == 12


def test_dashboard_page_served(client):
    res = client.get("/dashboard")
    assert res.status_code == 200
    assert "agentGrid" in res.text
    assert "btnGenerateReport" in res.text


def test_diagnostics_qa_gate_runs(client):
    """Regression test: BaseAgent.finish_run() previously rejected the
    qa_result kwarg passed by agents/quality.py, so every diagnostic silently
    failed QA. This asserts the gate actually completes and approves."""
    res = client.post(
        "/bi/diagnostics",
        json={"metrics": {"revenue": 100000, "expenses": 80000, "churn_rate": 0.05}},
        headers=HEADERS,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["qa"] is not None
    assert body["qa"]["status"] == "completed"
    assert body["qa"]["qa_result"] == "APPROVED"


def test_reports_markdown_from_task(client):
    diag = client.post(
        "/bi/diagnostics",
        json={"metrics": {"revenue": 100000, "expenses": 80000, "churn_rate": 0.05}},
        headers=HEADERS,
    ).json()
    task_id = diag["task_id"]

    res = client.post("/bi/reports", json={"task_id": task_id, "format": "markdown"}, headers=HEADERS)
    assert res.status_code == 200
    body = res.json()
    assert body["format"] == "markdown"
    assert "# CINTEXA Business Intelligence Report" in body["content"]
    # No leaked Python/Enum reprs in the rendered report
    assert "ConfidenceLevel." not in body["content"]
    assert "<ConfidenceReason" not in body["content"]


def test_reports_html_from_task(client):
    diag = client.post(
        "/bi/diagnostics",
        json={"metrics": {"revenue": 50000, "expenses": 40000}},
        headers=HEADERS,
    ).json()
    task_id = diag["task_id"]

    res = client.post("/bi/reports", json={"task_id": task_id, "format": "html"}, headers=HEADERS)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/html")
    assert "<h1>" in res.text


def test_reports_json_from_sections(client):
    res = client.post(
        "/bi/reports",
        json={"title": "Ad-hoc", "format": "json", "sections": {"executive_summary": "All good."}},
        headers=HEADERS,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "Ad-hoc"
    assert body["sections"]["executive_summary"] == "All good."


def test_reports_requires_task_id_or_sections(client):
    res = client.post("/bi/reports", json={"format": "markdown"}, headers=HEADERS)
    assert res.status_code == 400


def test_reports_unknown_task_id_404s(client):
    res = client.post("/bi/reports", json={"task_id": "TASK-does-not-exist"}, headers=HEADERS)
    assert res.status_code == 404


def test_get_report_for_task(client):
    diag = client.post(
        "/bi/diagnostics",
        json={"metrics": {"revenue": 20000}},
        headers=HEADERS,
    ).json()
    task_id = diag["task_id"]

    res = client.get(f"/bi/reports/{task_id}", params={"format": "json"}, headers=HEADERS)
    assert res.status_code == 200
    assert res.json()["report_type"] == "management"
    assert "sections" in res.json()

    res_md = client.get(f"/bi/reports/{task_id}", headers=HEADERS)
    assert res_md.status_code == 200
    assert res_md.json()["format"] == "markdown"


def test_mission_sse_stream_regression(client):
    """Regression test: api/main.py's mission_event_stream() built its final
    SSE payload with a backslash-escaped-quote f-string
    (f'...{json.dumps({\\"event_type\\": ...})}...'), which is an invalid
    Python f-string and raised SyntaxError on import — breaking every route
    in the app, not just this one. Asserts the module imports (implicit, by
    this test running at all) and the stream terminates with a stream.end
    event whose payload actually parses as JSON."""
    mission = client.post(
        "/bi/missions",
        json={"objective": "Assess my business health"},
        headers=HEADERS,
    ).json()
    mission_id = mission["mission_id"]

    with client.stream("GET", f"/bi/missions/{mission_id}/stream", headers=HEADERS) as res:
        assert res.status_code == 200
        raw = "".join(res.iter_text())

    events = [
        json.loads(line[len("data: "):])
        for line in raw.splitlines()
        if line.startswith("data: ")
    ]
    assert events, "expected at least one SSE event"
    assert events[-1]["event_type"] == "stream.end"
    assert events[-1]["status"] == mission["status"]


def test_mission_report_reflects_real_synthesis(client):
    """Regression test: mission.result is a MissionResult pydantic model
    (see WorkforceOrchestrator.synthesise in orchestrator/workforce.py), not
    a plain dict. The first cut of _mission_report_sections() checked
    isinstance(mission.result, dict), which is always False for a pydantic
    model, so every mission report silently fell back to a one-line
    placeholder ("Mission '...' is currently COMPLETED.") instead of the
    real findings/summary. Assert the actual synthesis content is present."""
    mission = client.post(
        "/bi/missions",
        json={"objective": "Assess my business health"},
        headers=HEADERS,
    ).json()
    mission_id = mission["mission_id"]

    res = client.get(f"/bi/missions/{mission_id}/report", headers=HEADERS)
    assert res.status_code == 200
    content = res.json()["content"]
    assert "is currently COMPLETED." not in content  # the placeholder fallback text
    assert "Findings" in content or "findings" in content.lower()


def test_mission_report_json_and_html(client):
    mission = client.post(
        "/bi/missions",
        json={"objective": "Analyse my market"},
        headers=HEADERS,
    ).json()
    mission_id = mission["mission_id"]

    res_json = client.get(f"/bi/missions/{mission_id}/report", params={"format": "json"}, headers=HEADERS)
    assert res_json.status_code == 200

    res_html = client.get(f"/bi/missions/{mission_id}/report", params={"format": "html"}, headers=HEADERS)
    assert res_html.status_code == 200
    assert res_html.headers["content-type"].startswith("text/html")


def test_mission_report_unknown_mission_404s(client):
    res = client.get("/bi/missions/MISSION-does-not-exist/report", headers=HEADERS)
    assert res.status_code == 404


def test_reports_post_accepts_mission_id(client):
    mission = client.post(
        "/bi/missions",
        json={"objective": "Research my competitors"},
        headers=HEADERS,
    ).json()

    res = client.post(
        "/bi/reports",
        json={"mission_id": mission["mission_id"], "format": "markdown"},
        headers=HEADERS,
    )
    assert res.status_code == 200
    assert "# CINTEXA Business Intelligence Report" in res.json()["content"]


def test_reports_post_error_message_mentions_mission_id(client):
    """The 400 error should mention all three valid options now that
    mission_id is supported, not just the original task_id/sections pair."""
    res = client.post("/bi/reports", json={"format": "markdown"}, headers=HEADERS)
    assert res.status_code == 400
    assert "mission_id" in res.json()["detail"]


def test_events_bus_records_lifecycle(client):
    """Regression test for the events.bus wiring: diagnostic + QA lifecycle
    events should be recorded and scoped to the caller's organisation."""
    client.post(
        "/bi/diagnostics",
        json={"metrics": {"revenue": 30000}},
        headers=HEADERS,
    )
    res = client.get("/bi/events", headers=HEADERS)
    assert res.status_code == 200
    types = {e["event_type"] for e in res.json()}
    assert "diagnostic.started" in types
    assert "diagnostic.completed" in types
    assert "qa.started" in types
    assert "qa.completed" in types
    assert all(e["organisation_id"] == "default-org" for e in res.json())
