"""Unit tests for individual agents."""

import pytest
from agents.diagnostic import BusinessDiagnosticAgent
from agents.forecasting import ForecastingAgent
from agents.quality import QualityAssuranceAgent
from agents.intelligence import BusinessIntelligenceAgent
from agents.decision import DecisionSupportAgent
from agents.memory import MemoryAgent
from agents.knowledge import KnowledgeManagerAgent


@pytest.mark.asyncio
async def test_diagnostic_with_metrics():
    agent = BusinessDiagnosticAgent()
    result = await agent.execute(
        "TASK-1",
        {"organisation_id": "org1"},
        {"request": "health check", "metrics": {"revenue": 100000, "nps": 50, "gross_margin": 0.4}},
    )
    assert result["status"] == "completed"
    findings = result["findings"]
    assert "pillars" in findings
    assert findings.get("overall_score") is not None or findings.get("missing_information")


@pytest.mark.asyncio
async def test_diagnostic_without_metrics():
    agent = BusinessDiagnosticAgent()
    result = await agent.execute("TASK-2", {"organisation_id": "org1"}, {"request": "health"})
    assert result["status"] == "completed"
    assert "findings" in result


@pytest.mark.asyncio
async def test_forecast_requires_history():
    agent = ForecastingAgent()
    result = await agent.execute("TASK-3", {}, {"request": "forecast"})
    assert result["status"] == "completed"
    assert "unavailable" in result["summary"].lower() or "limitations" in str(result.get("findings", {}))


@pytest.mark.asyncio
async def test_forecast_with_series():
    agent = ForecastingAgent()
    result = await agent.execute(
        "TASK-4",
        {},
        {"historical_series": {"revenue": [1, 2, 3, 4, 5, 6]}, "horizon_months": 3},
    )
    assert result["status"] == "completed"
    findings = result["findings"]
    assert "methodology" in findings
    assert "uncertainty" in findings or "projected_range" in findings


@pytest.mark.asyncio
async def test_intelligence_no_data():
    agent = BusinessIntelligenceAgent()
    result = await agent.execute("TASK-5", {}, {})
    assert result["status"] == "completed"
    assert "No business metrics" in result["summary"] or result["findings"].get("missing")


@pytest.mark.asyncio
async def test_decision_informs_not_decides():
    agent = DecisionSupportAgent()
    result = await agent.execute(
        "TASK-6",
        {},
        {"decision": "Expand to EU?", "options": ["Yes", "No"]},
    )
    assert result["status"] == "completed"
    note = result["findings"].get("note", "")
    assert "does not make the decision" in note.lower() or "informs" in note.lower()


@pytest.mark.asyncio
async def test_memory_categories_enforced():
    agent = MemoryAgent()
    result = await agent.execute(
        "TASK-7",
        {"organisation_id": "org1", "task_id": "TASK-7"},
        {"action": "store", "category": "invalid_cat", "content": "x"},
    )
    assert result.get("status") == "failed"


@pytest.mark.asyncio
async def test_knowledge_index_and_retrieve():
    agent = KnowledgeManagerAgent()
    await agent.execute(
        "TASK-8",
        {"organisation_id": "org1"},
        {"action": "index", "title": "Policy A", "content": "Return policy details"},
    )
    result = await agent.execute(
        "TASK-9",
        {"organisation_id": "org1"},
        {"action": "retrieve", "query": "return"},
    )
    assert result["status"] == "completed"
    assert len(result["findings"]["items"]) >= 1


@pytest.mark.asyncio
async def test_qa_approves_clean_output():
    agent = QualityAssuranceAgent()
    result = await agent.execute(
        "TASK-10",
        {
            "prior_results": {
                "diagnostic": {
                    "status": "completed",
                    "findings": {"methodology": "transparent scoring", "pillars": []},
                    "evidence_ids": [],
                }
            }
        },
        {},
    )
    assert result["qa_result"] in ("APPROVED", "REVISION_REQUIRED")
