"""HTTP-level regression tests for the FastAPI app — covers the QA gate wiring
and the /bi/reports endpoint (added to expose the previously-unwired
reports.generator module)."""

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
