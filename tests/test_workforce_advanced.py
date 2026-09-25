
"""Advanced workforce orchestrator tests — gates, VoI, cache, recovery, DAG."""

import asyncio
import pytest

from orchestrator.cache import ResultCache
from orchestrator.conflict_manager import ConflictManager
from orchestrator.dependency_graph import DependencyGraph
from orchestrator.evidence_gate import EvidenceGate
from orchestrator.information_value import information_value
from orchestrator.quality_gate import quality_gate
from orchestrator.recovery_manager import recovery_manager
from orchestrator.stopping_engine import StoppingEngine
from orchestrator.policies import DEFAULT_POLICIES
from orchestrator.workforce import WorkforceOrchestrator
from schemas.missions import (
    EvidenceSufficiency,
    FailureClass,
    Mission,
    MissionCreate,
    MissionStatus,
    MissionTask,
    MissionTaskStatus,
    MissionPriority,
)


def test_evidence_gate_levels():
    gate = EvidenceGate()
    assert gate.evaluate([]) == EvidenceSufficiency.INSUFFICIENT
    assert gate.evaluate([{"confidence": 0.9}] * 5) in (
        EvidenceSufficiency.STRONG,
        EvidenceSufficiency.VERY_STRONG,
    )


def test_information_value():
    gaps = information_value.evaluate(["historical_metrics", "competitor_pricing"])
    assert gaps
    assert any(g.name == "historical_metrics" for g in gaps)


def test_recovery_classify():
    assert recovery_manager.classify(TimeoutError("timeout")) == FailureClass.TIMEOUT
    assert recovery_manager.should_retry(FailureClass.TIMEOUT, 1, 3) is True
    assert recovery_manager.should_retry(FailureClass.PERMISSION_FAILURE, 0, 3) is False


def test_cache_ttl():
    c = ResultCache()
    c.set("org1", "profile", {"name": "Acme"}, ttl_seconds=60, confidence=0.9)
    assert c.get("org1", "profile")["name"] == "Acme"


def test_conflict_detection():
    cm = ConflictManager()
    conflicts = cm.detect(
        {
            "sales": {"primary_driver": "churn"},
            "market": {"primary_driver": "demand decline"},
        }
    )
    assert conflicts
    resolved = cm.resolve(conflicts[0])
    assert resolved.resolution_status.value != ""


def test_quality_gates_on_empty_mission():
    m = Mission(objective="test", organisation_id="o")
    gates = quality_gate.run_all(m)
    assert any(g.gate == "planning" for g in gates)


@pytest.mark.asyncio
async def test_revenue_decline_scenario():
    wf = WorkforceOrchestrator()
    m = await wf.create_and_run(
        MissionCreate(
            objective="Find out why our sales declined during the last six months and create a recovery strategy",
            organisation_id="scenario-org",
            context={"industry": "retail", "metrics": {"revenue_change_pct": -18}},
            priority=MissionPriority.HIGH,
        ),
        auto_run=True,
    )
    assert m.mission_id
    assert m.plan_version >= 1
    assert m.assigned_agents
    # Should not be stuck in CREATED
    assert m.status != MissionStatus.CREATED
    trace = wf.trace(m.mission_id)
    assert "mission_id" in trace
    if m.status == MissionStatus.COMPLETED:
        assert m.result is not None
        assert m.result.summary


@pytest.mark.asyncio
async def test_pause_resume_cancel_lifecycle():
    wf = WorkforceOrchestrator()
    m = await wf.create_and_run(
        MissionCreate(objective="Analyse market opportunity for SMB tools", organisation_id="life-org"),
        auto_run=False,
    )
    m = await wf.pause(m.mission_id)
    assert m.status == MissionStatus.PAUSED
    m = await wf.cancel(m.mission_id)
    assert m.status == MissionStatus.CANCELLED
