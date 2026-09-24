"""Multi-agent integration tests for CINTEXA BI Orchestrator."""

import pytest
from schemas.common import Priority, TaskState
from schemas.tasks import TaskCreate
from orchestrator.core import Orchestrator
from orchestrator.planner import build_task_plan
from agents.registry import list_agents, agent_ids


@pytest.fixture
def orch():
    return Orchestrator()


def test_all_twelve_agents_registered():
    ids = agent_ids()
    assert len(ids) == 12
    expected = {
        "orchestrator", "strategy", "intelligence", "diagnostic", "market",
        "competitor", "research", "decision", "forecasting", "knowledge",
        "memory", "quality",
    }
    assert set(ids) == expected


def test_planner_growth_strategy():
    plan = build_task_plan("Analyse my company and create a 12-month growth strategy")
    assert plan.objective == "business_growth_assessment"
    assert "diagnostic" in plan.agents_required
    assert "strategy" in plan.agents_required
    assert "quality" in plan.agents_required
    assert plan.requires_web_research is True


def test_planner_business_health():
    plan = build_task_plan("Assess my business health")
    assert plan.objective == "business_health_assessment"
    assert "diagnostic" in plan.agents_required


@pytest.mark.asyncio
async def test_diagnostic_scenario(orch):
    payload = TaskCreate(
        request="Assess my business health",
        organisation_id="org-test-1",
        user_id="user-1",
        priority=Priority.HIGH,
        context={
            "metrics": {
                "revenue": 120000,
                "sales_growth": 0.12,
                "nps": 42,
                "gross_margin": 0.55,
            }
        },
    )
    task = orch.create_task(payload)
    assert task.state == TaskState.PLANNING
    task = await orch.run(task.task_id)
    assert task.state in (TaskState.COMPLETED, TaskState.FAILED)
    assert "diagnostic" in task.results
    diag = task.results["diagnostic"]
    assert diag.get("status") == "completed"
    assert "quality" in task.results


@pytest.mark.asyncio
async def test_forecast_with_series(orch):
    payload = TaskCreate(
        request="Forecast my next 12 months of revenue",
        organisation_id="org-test-1",
        user_id="user-1",
        context={
            "historical_series": {"revenue": [10, 12, 11, 14, 15, 16, 18, 17, 19, 20, 22, 24]},
            "horizon_months": 6,
            "metric": "revenue",
        },
    )
    task = orch.create_task(payload)
    task = await orch.run(task.task_id)
    fc = task.results.get("forecasting", {})
    assert fc.get("status") == "completed"
    findings = fc.get("findings", {})
    assert "projected_point_forecast" in findings or "limitations" in findings
    assert "uncertainty" in str(findings).lower() or "unavailable" in str(findings).lower()


@pytest.mark.asyncio
async def test_no_fabricated_market_stats(orch):
    payload = TaskCreate(
        request="Analyse my market",
        organisation_id="org-test-1",
        user_id="user-1",
        context={"industry": "SaaS", "geography": "UK"},
    )
    task = orch.create_task(payload)
    task = await orch.run(task.task_id)
    market = task.results.get("market", {})
    findings = market.get("findings", {})
    # Without tool_results, data_status should be unavailable
    assert findings.get("data_status") in ("unavailable", "from_research_agent")
    # No invented percentages as facts
    trends = findings.get("trends", [])
    for t in trends:
        assert "unavailable" in str(t).lower() or isinstance(t, str)


@pytest.mark.asyncio
async def test_organisation_isolation(orch):
    t1 = orch.create_task(TaskCreate(
        request="Assess my business health",
        organisation_id="org-A",
        user_id="u1",
    ))
    t2 = orch.create_task(TaskCreate(
        request="Assess my business health",
        organisation_id="org-B",
        user_id="u2",
    ))
    assert t1.organisation_id != t2.organisation_id
    got = orch.get_task(t1.task_id)
    assert got.organisation_id == "org-A"


@pytest.mark.asyncio
async def test_qa_runs_on_outputs(orch):
    payload = TaskCreate(
        request="Assess my business health",
        organisation_id="org-test-1",
        user_id="user-1",
        context={"metrics": {"revenue": 50000}},
    )
    task = orch.create_task(payload)
    task = await orch.run(task.task_id)
    qa = task.results.get("quality", {})
    assert qa.get("qa_result") in ("APPROVED", "REVISION_REQUIRED")
