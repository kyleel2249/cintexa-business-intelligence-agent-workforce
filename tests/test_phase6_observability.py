"""Phase 6 Observability & Evaluation tests."""

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


def test_redact_secrets():
    from observability.logging import redact_secrets

    s = redact_secrets({"api_key": "sk-abc1234567890", "ok": "fine"})
    assert s["api_key"] == "[REDACTED]"
    assert s["ok"] == "fine"
    assert "sk-" not in redact_secrets("token sk-abcdefghijklmnop leaked")


def test_trace_and_tenant_isolation(db_ready):
    from observability.context import TelemetryContext, set_context, with_span
    from observability.tracing import tracer

    ctx = TelemetryContext(organisation_id="org-a", correlation_id="c1").ensure_ids()
    set_context(ctx)
    with with_span("agent.execute", component="agent", agent="research"):
        with with_span("tool.http", component="tool"):
            pass
    timeline = tracer.timeline(ctx.trace_id, "org-a")
    assert timeline["span_count"] >= 2
    # org-b should not see org-a spans when filtered
    other = tracer.timeline(ctx.trace_id, "org-b")
    assert other["span_count"] == 0 or all(
        s.get("organisation_id") in (None, "org-b") for s in other["spans"]
    )


def test_metrics_histogram(db_ready):
    from observability.metrics import MetricsRegistry

    m = MetricsRegistry()
    for v in [10, 20, 30, 40, 100]:
        m.observe("latency_ms", v, "org1")
    m.incr("requests", "org1")
    snap = m.snapshot("org1")
    h = snap["histograms"]["latency_ms|org1"]
    assert h["count"] == 5
    assert h["p50"] <= h["p95"]
    assert snap["counters"]["requests|org1"] == 1


def test_evaluation_pass_fail_unknown(db_ready):
    from observability.evaluation import EvaluationEngine

    eng = EvaluationEngine()
    ds = eng.create_dataset("org-e", "golden")
    cases = [
        {
            "case_id": "c1",
            "input": "What is 2+2?",
            "expected_output": "4",
            "required_facts": ["4"],
        },
        {
            "case_id": "c2",
            "input": "hallucinate",
            "expected_output": "correct",
            "forbidden_claims": ["secret-password"],
        },
        {"case_id": "c3", "input": "open"},  # nothing to measure
    ]
    ver = eng.publish_version("org-e", ds["dataset_id"], "v1", cases)

    def executor(case):
        if case["case_id"] == "c1":
            return "The answer is 4"
        if case["case_id"] == "c2":
            return "wrong answer without secret"
        return "whatever"

    run = eng.run_dataset("org-e", ver["version_id"], executor)
    assert run["cases_passed"] >= 1
    assert run["cases_failed"] >= 1
    assert run["cases_unknown"] >= 1


def test_regression_detection(db_ready):
    from observability.evaluation import EvaluationEngine

    eng = EvaluationEngine()
    ds = eng.create_dataset("org-reg", "r")
    cases = [{"case_id": "x", "expected_output": "yes"}]
    ver = eng.publish_version("org-reg", ds["dataset_id"], "v1", cases)
    good = eng.run_dataset("org-reg", ver["version_id"], lambda c: "yes")
    bad = eng.run_dataset("org-reg", ver["version_id"], lambda c: "no")
    reg = eng.detect_regression("org-reg", good["run_id"], bad["run_id"])
    assert reg["regressed"] is True


def test_replay_readonly(db_ready):
    from observability.context import TelemetryContext, set_context, with_span
    from observability.replay import ReplayService
    from observability.tracing import tracer
    from core.errors import ValidationError

    ctx = TelemetryContext(organisation_id="org-rp").ensure_ids()
    set_context(ctx)
    with with_span("work", component="wf"):
        pass
    rs = ReplayService()
    with pytest.raises(ValidationError):
        rs.create("org-rp", mode="PRODUCTION_WRITE")
    r = rs.create("org-rp", source_trace_id=ctx.trace_id, mode="READ_ONLY_REPLAY")
    out = rs.run_readonly("org-rp", r["replay_id"])
    assert out["status"] == "COMPLETED"
    assert out["side_effects"] == "none"
    # cross-tenant
    with pytest.raises(Exception):
        rs.run_readonly("other", r["replay_id"])


def test_e2e_correlated_pipeline(db_ready):
    from observability.context import TelemetryContext, set_context, with_span
    from observability.logging import structured_log
    from observability.metrics import metrics
    from observability.evaluation import EvaluationEngine
    from observability.tracing import tracer

    ctx = TelemetryContext(
        organisation_id="org-e2e", user_id="u1", workflow_id="wf1", task_id="t1"
    ).ensure_ids()
    set_context(ctx)
    with with_span("workflow.run", component="workflow"):
        structured_log("INFO", "workflow started", component="workflow")
        with with_span("agent.execute", component="agent"):
            with with_span("knowledge.retrieve", component="knowledge"):
                pass
            with with_span("model.complete", component="model"):
                pass
            with with_span("tool.run", component="tool"):
                pass
        structured_log("INFO", "workflow completed", component="workflow", status="OK")

    tl = tracer.timeline(ctx.trace_id, "org-e2e")
    assert tl["span_count"] >= 4
    assert any(s["operation"] == "agent.execute" for s in tl["spans"])

    eng = EvaluationEngine()
    ds = eng.create_dataset("org-e2e", "e2e")
    ver = eng.publish_version(
        "org-e2e",
        ds["dataset_id"],
        "v1",
        [{"case_id": "1", "expected_output": "done", "required_facts": ["done"]}],
    )
    run = eng.run_dataset("org-e2e", ver["version_id"], lambda c: "workflow done")
    eng.update_quality_profile(
        "org-e2e",
        "workflow",
        "wf1",
        {"pass_rate": run["cases_passed"] / max(1, run["cases_total"]), "trace_id": ctx.trace_id},
    )
    assert run["cases_passed"] == 1
    metrics.incr("e2e.completed", "org-e2e")


def test_alert_and_defect(db_ready):
    from observability.alerts import AlertService, IncidentService
    from observability.evaluation import EvaluationEngine

    a = AlertService().fire("org-a", rule="manual", severity="WARNING", message="test")
    assert a["alert_id"]
    assert any(x["alert_id"] == a["alert_id"] for x in AlertService().list_open("org-a"))
    assert AlertService().list_open("org-b") == []
    IncidentService().create("org-a", "spike", severity="HIGH")
    EvaluationEngine().create_defect("org-a", "bad output", expected="x", actual="y")
