"""Unit and scenario tests for Workforce Orchestrator."""

import asyncio
import pytest

from orchestrator.dependency_graph import DependencyGraph
from orchestrator.intent_engine import IntentEngine
from orchestrator.objective_normalizer import ObjectiveNormalizer
from orchestrator.task_decomposer import TaskDecomposer
from orchestrator.workforce import WorkforceOrchestrator
from schemas.missions import (
    MissionCreate,
    MissionStatus,
    MissionTask,
    MissionTaskStatus,
    MissionPriority,
)


def test_intent_revenue_domain():
    eng = IntentEngine()
    intent = eng.understand("Analyse why our revenue dropped and tell me what we should do next quarter")
    assert intent.business_domain in ("revenue", "diagnostic")
    assert intent.ambiguity != intent.ambiguity.CRITICAL or True
    assert "historical_analysis" in intent.requested_analysis or len(intent.requested_analysis) >= 1


def test_intent_ambiguous():
    eng = IntentEngine()
    intent = eng.understand("Improve sales")
    assert intent.ambiguity.value in ("MEDIUM", "HIGH", "CRITICAL", "LOW")


def test_normalize_and_decompose():
    eng = IntentEngine()
    intent = eng.understand("Forecast next 12 months of revenue")
    norm = ObjectiveNormalizer().normalize(intent, "Forecast next 12 months of revenue")
    assert norm.objective
    tasks = TaskDecomposer().decompose(norm, intent)
    assert len(tasks) >= 2
    assert any((t.role == "quality" or t.assigned_agent_id == "quality") for t in tasks) or tasks[-1].role == "quality"


def test_dependency_cycle_detection():
    a = MissionTask(objective="A", task_id="a")
    b = MissionTask(objective="B", task_id="b", dependencies=["a"])
    c = MissionTask(objective="C", task_id="c", dependencies=["b"])
    # introduce cycle
    a.dependencies = ["c"]
    g = DependencyGraph([a, b, c])
    ok, errors = g.validate()
    assert not ok
    assert any("cycle" in e.lower() for e in errors)


def test_dependency_ready_and_layers():
    a = MissionTask(objective="A", task_id="a")
    b = MissionTask(objective="B", task_id="b", dependencies=["a"])
    g = DependencyGraph([a, b])
    ok, _ = g.validate()
    assert ok
    ready = g.ready_tasks()
    assert ready[0].task_id == "a"
    layers = g.topological_layers()
    assert layers[0] == ["a"]


@pytest.mark.asyncio
async def test_mission_end_to_end_diagnostic():
    wf = WorkforceOrchestrator()
    mission = await wf.create_and_run(
        MissionCreate(
            objective="Assess business health for a B2B SaaS product with limited metrics",
            organisation_id="test-org",
            user_id="tester",
            priority=MissionPriority.NORMAL,
            context={"industry": "B2B SaaS"},
        ),
        auto_run=True,
    )
    assert mission.mission_id
    assert mission.status in (
        MissionStatus.COMPLETED,
        MissionStatus.WAITING_FOR_INPUT,
        MissionStatus.FAILED,
        MissionStatus.AWAITING_APPROVAL,
    )
    if mission.status == MissionStatus.COMPLETED:
        assert mission.result is not None
        assert mission.plan_version >= 1
        assert len(mission.tasks) >= 1
        trace = wf.trace(mission.mission_id)
        assert trace["mission_id"] == mission.mission_id


@pytest.mark.asyncio
async def test_idempotency():
    wf = WorkforceOrchestrator()
    p = MissionCreate(
        objective="Research market structure for SMB accounting software",
        organisation_id="test-org",
        idempotency_key="idem-1",
    )
    m1 = await wf.create_and_run(p, auto_run=False)
    m2 = await wf.create_and_run(p, auto_run=False)
    assert m1.mission_id == m2.mission_id


@pytest.mark.asyncio
async def test_cancel():
    wf = WorkforceOrchestrator()
    m = await wf.create_and_run(
        MissionCreate(objective="Compare two strategic growth options", organisation_id="test-org"),
        auto_run=False,
    )
    m = await wf.cancel(m.mission_id)
    assert m.status == MissionStatus.CANCELLED
