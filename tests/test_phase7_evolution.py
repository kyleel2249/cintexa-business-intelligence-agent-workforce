"""Phase 7 Controlled Evolution tests."""

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
    import evolution.models_db  # noqa: F401

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


def test_proposal_requires_evidence(db_ready):
    from evolution.proposals import ProposalService
    from core.errors import ValidationError

    with pytest.raises(ValidationError):
        ProposalService().create(
            "org1",
            title="t",
            category="PROMPT_IMPROVEMENT",
            proposed_change={"prompt": "x"},
            evidence=None,
        )


def test_self_approval_blocked(db_ready):
    from evolution.proposals import ProposalService
    from evolution.approval import ApprovalEngine
    from core.errors import AuthorizationError

    p = ProposalService().create(
        "org1",
        title="prompt tweak",
        category="PROMPT_IMPROVEMENT",
        proposed_change={"prompt": "v2"},
        evidence={"failures": 3},
    )
    with pytest.raises(AuthorizationError):
        ApprovalEngine().approve("org1", p["proposal_id"], approver="self", role="system")


def test_low_risk_auto_approve_and_stage(db_ready):
    from evolution.proposals import ProposalService
    from evolution.approval import ApprovalEngine
    from evolution.deployment import DeploymentEngine

    p = ProposalService().create(
        "org1",
        title="doc update",
        category="DOCUMENTATION_UPDATE",
        proposed_change={"doc": "PHASE_7 note"},
        evidence={"observation": "docs stale"},
    )
    auto = ApprovalEngine().auto_approve_if_allowed("org1", p["proposal_id"])
    assert auto is not None
    rel = DeploymentEngine().stage("org1", p["proposal_id"], version="1.0.0")
    assert rel["status"] == "STAGED"
    can = DeploymentEngine().canary("org1", rel["release_id"], 10)
    assert can["canary_percent"] == 10
    rb = DeploymentEngine().rollback("org1", rel["release_id"], reason="test")
    assert rb["status"] == "ROLLED_BACK"


def test_approval_invalidated_on_modify(db_ready):
    from evolution.proposals import ProposalService
    from evolution.approval import ApprovalEngine
    from evolution.deployment import DeploymentEngine
    from core.errors import AuthorizationError

    p = ProposalService().create(
        "org1",
        title="prompt",
        category="PROMPT_IMPROVEMENT",
        proposed_change={"prompt": "a"},
        evidence={"n": 1},
    )
    ApprovalEngine().approve("org1", p["proposal_id"], approver="alice", role="human")
    ProposalService().update_change(p["proposal_id"], "org1", {"prompt": "b"})
    # fix arg order - update_change(proposal_id, organisation_id)
    # check signature
    with pytest.raises(AuthorizationError):
        DeploymentEngine().stage("org1", p["proposal_id"], version="1.0.1")


def test_experiment_regression(db_ready):
    from evolution.experiments import ExperimentEngine

    eng = ExperimentEngine()
    exp = eng.create(
        "org1",
        hypothesis="candidate better",
        baseline={"name": "base"},
        candidate={"name": "cand"},
        success_criteria={"min_pass_rate_delta": 0.0},
        failure_criteria={"max_fail_rate_increase": 0.05},
    )
    cases = [{"case_id": "1", "expected_output": "yes"}]
    out = eng.run_offline(
        "org1",
        exp["experiment_id"],
        baseline_executor=lambda c: "yes",
        candidate_executor=lambda c: "no",
        cases=cases,
    )
    assert out["conclusion"] == "REGRESSED"
    assert out["results"]["production_affected"] is False


def test_prohibited_category_self_mod(db_ready):
    from evolution.governance import is_prohibited
    from evolution.proposals import ProposalService
    from evolution.approval import ApprovalEngine
    from core.errors import AuthorizationError

    assert is_prohibited("TENANT_ISOLATION")
    p = ProposalService().create(
        "org1",
        title="weaken isolation",
        category="TENANT_ISOLATION",
        proposed_change={"disable": True},
        evidence={"note": "bad idea"},
    )
    with pytest.raises(AuthorizationError):
        ApprovalEngine().approve(
            "org1", p["proposal_id"], approver="bob", role="human", decision="APPROVED"
        )


def test_freeze_and_emergency_stop(db_ready):
    from evolution.governance import change_freeze
    from evolution.proposals import ProposalService
    from evolution.deployment import DeploymentEngine
    from evolution.approval import ApprovalEngine
    from core.errors import AuthorizationError

    change_freeze.clear_emergency(authorized=True)
    change_freeze.unfreeze()
    p = ProposalService().create(
        "org1",
        title="x",
        category="PROMPT_IMPROVEMENT",
        proposed_change={"p": 1},
        evidence={"e": 1},
    )
    ApprovalEngine().approve("org1", p["proposal_id"], approver="alice", role="human")
    change_freeze.freeze("incident")
    with pytest.raises(AuthorizationError):
        DeploymentEngine().stage("org1", p["proposal_id"], version="9")
    change_freeze.unfreeze()
    change_freeze.emergency("breach")
    with pytest.raises(AuthorizationError):
        ProposalService().create(
            "org1",
            title="y",
            category="PROMPT_IMPROVEMENT",
            proposed_change={"p": 2},
            evidence={"e": 1},
        )
    change_freeze.clear_emergency(authorized=True)


def test_knowledge_not_auto_promoted(db_ready):
    from evolution.learning import KnowledgePromotion
    from core.errors import AuthorizationError

    kp = KnowledgePromotion()
    c = kp.propose("org1", "fact from model", {"source": "agent"}, trust="AGENT_DERIVED")
    assert c["status"] == "CANDIDATE"
    with pytest.raises(AuthorizationError):
        kp.promote("org1", c["candidate_id"], authorized=False)


def test_cross_tenant_proposal_hidden(db_ready):
    from evolution.proposals import ProposalService

    p = ProposalService().create(
        "orgA",
        title="a",
        category="PROMPT_IMPROVEMENT",
        proposed_change={"x": 1},
        evidence={"e": 1},
    )
    assert ProposalService().get(p["proposal_id"], "orgB") is None


def test_disable_evaluation_blocked(db_ready):
    from evolution.proposals import ProposalService
    from evolution.approval import ApprovalEngine
    from evolution.governance import risk_for, RiskLevel, is_prohibited
    from core.errors import AuthorizationError

    assert is_prohibited("DISABLE_EVALUATION")
    assert risk_for("DISABLE_EVALUATION") == RiskLevel.LEVEL_4
    p = ProposalService().create(
        "org1",
        title="disable eval",
        category="DISABLE_EVALUATION",
        proposed_change={"disable": True},
        evidence={"note": "attack"},
    )
    with pytest.raises(AuthorizationError):
        ApprovalEngine().approve("org1", p["proposal_id"], approver="bob", role="human")
