"""Governance policies and hard boundaries for self-improvement."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Set


class RiskLevel(str, Enum):
    LEVEL_0 = "LEVEL_0"  # informational
    LEVEL_1 = "LEVEL_1"  # low — prompt/config limited
    LEVEL_2 = "LEVEL_2"  # moderate — agent/workflow/retrieval
    LEVEL_3 = "LEVEL_3"  # high — code/tools/db
    LEVEL_4 = "LEVEL_4"  # critical — security/auth/tenant


# Categories that may never auto-change without explicit human CRITICAL approval path
PROHIBITED_AUTO_CATEGORIES: Set[str] = {
    "SECURITY_POLICY",
    "AUTHENTICATION",
    "AUTHORIZATION",
    "TENANT_ISOLATION",
    "AUDIT_CONTROL",
    "SECRETS",
    "CREDENTIALS",
    "GOVERNANCE",
    "FINANCIAL_CONTROL",
    "PRODUCTION_INFRASTRUCTURE",
    "DISABLE_EVALUATION",
    "DISABLE_OBSERVABILITY",
    "REMOVE_REGRESSION_TESTS",
    "SELF_APPROVAL",
    "PERMISSION_ESCALATION",
}


CATEGORY_RISK = {
    "PROMPT_IMPROVEMENT": RiskLevel.LEVEL_1,
    "AGENT_CONFIGURATION": RiskLevel.LEVEL_2,
    "AGENT_ROUTING": RiskLevel.LEVEL_2,
    "WORKFLOW_OPTIMIZATION": RiskLevel.LEVEL_2,
    "RETRIEVAL_OPTIMIZATION": RiskLevel.LEVEL_2,
    "KNOWLEDGE_UPDATE": RiskLevel.LEVEL_2,
    "TOOL_SELECTION": RiskLevel.LEVEL_2,
    "TOOL_CONFIGURATION": RiskLevel.LEVEL_2,
    "MODEL_ROUTING": RiskLevel.LEVEL_2,
    "MODEL_CONFIGURATION": RiskLevel.LEVEL_2,
    "EVALUATION_IMPROVEMENT": RiskLevel.LEVEL_1,
    "TEST_COVERAGE": RiskLevel.LEVEL_1,
    "RELIABILITY_POLICY": RiskLevel.LEVEL_2,
    "RETRY_POLICY": RiskLevel.LEVEL_2,
    "TIMEOUT_POLICY": RiskLevel.LEVEL_2,
    "PERFORMANCE_OPTIMIZATION": RiskLevel.LEVEL_2,
    "DOCUMENTATION_UPDATE": RiskLevel.LEVEL_0,
    "CODE_CHANGE": RiskLevel.LEVEL_3,
    "SCHEMA_CHANGE": RiskLevel.LEVEL_3,
    "DATABASE_CHANGE": RiskLevel.LEVEL_3,
    "INFRASTRUCTURE_CHANGE": RiskLevel.LEVEL_4,
    "SECURITY_HARDENING": RiskLevel.LEVEL_4,
    "SECURITY_POLICY": RiskLevel.LEVEL_4,
    "AUTHENTICATION": RiskLevel.LEVEL_4,
    "AUTHORIZATION": RiskLevel.LEVEL_4,
    "TENANT_ISOLATION": RiskLevel.LEVEL_4,
    "SECRETS": RiskLevel.LEVEL_4,
    "CREDENTIALS": RiskLevel.LEVEL_4,
    "GOVERNANCE": RiskLevel.LEVEL_4,
    "SELF_APPROVAL": RiskLevel.LEVEL_4,
    "DISABLE_EVALUATION": RiskLevel.LEVEL_4,
}


def is_prohibited(category: str) -> bool:
    return category.upper() in PROHIBITED_AUTO_CATEGORIES or category in PROHIBITED_AUTO_CATEGORIES


def risk_for(category: str) -> RiskLevel:
    if is_prohibited(category):
        return RiskLevel.LEVEL_4
    return CATEGORY_RISK.get(category, RiskLevel.LEVEL_2)


@dataclass
class GovernancePolicy:
    """What may auto-approve vs human-required."""

    allow_auto_approve_levels: Set[RiskLevel] = field(
        default_factory=lambda: {RiskLevel.LEVEL_0, RiskLevel.LEVEL_1}
    )
    require_human_levels: Set[RiskLevel] = field(
        default_factory=lambda: {RiskLevel.LEVEL_2, RiskLevel.LEVEL_3, RiskLevel.LEVEL_4}
    )
    frozen: bool = False
    emergency_stop: bool = False

    def may_auto_approve(self, risk: RiskLevel, category: str) -> bool:
        if self.frozen or self.emergency_stop:
            return False
        if is_prohibited(category):
            return False
        if risk in (RiskLevel.LEVEL_3, RiskLevel.LEVEL_4):
            return False
        return risk in self.allow_auto_approve_levels

    def may_deploy(self, risk: RiskLevel, category: str, approved: bool) -> bool:
        if self.frozen or self.emergency_stop:
            return False
        if is_prohibited(category) and risk == RiskLevel.LEVEL_4:
            # even approved prohibited categories need explicit human path — still require approved
            return approved
        return approved


# process-local freeze state; durable mirror in models
_freeze = ChangeFreeze = type("ChangeFreeze", (), {})  # placeholder overwritten below


class ChangeFreeze:
    def __init__(self):
        self.frozen = False
        self.emergency_stop = False
        self.reason = ""

    def freeze(self, reason: str = "manual") -> dict:
        self.frozen = True
        self.reason = reason
        return {"frozen": True, "reason": reason}

    def unfreeze(self) -> dict:
        if self.emergency_stop:
            from core.errors import AuthorizationError
            raise AuthorizationError("Cannot unfreeze while emergency stop is active")
        self.frozen = False
        self.reason = ""
        return {"frozen": False}

    def emergency(self, reason: str = "emergency") -> dict:
        self.emergency_stop = True
        self.frozen = True
        self.reason = reason
        return {"emergency_stop": True, "frozen": True, "reason": reason}

    def clear_emergency(self, *, authorized: bool = False) -> dict:
        if not authorized:
            from core.errors import AuthorizationError
            raise AuthorizationError("Clearing emergency stop requires authorization")
        self.emergency_stop = False
        self.frozen = False
        self.reason = ""
        return {"emergency_stop": False}

    def status(self) -> dict:
        return {
            "frozen": self.frozen,
            "emergency_stop": self.emergency_stop,
            "reason": self.reason,
        }


change_freeze = ChangeFreeze()
default_policy = GovernancePolicy()


def _sync_durable_freeze():
    """Best-effort sync process freeze to durable store for multi-worker visibility."""
    try:
        from cintexa_platform.coordination import DurableFreeze
        df = DurableFreeze()
        st = change_freeze.status()
        if st.get("emergency_stop"):
            df.emergency(st.get("reason") or "", by="process")
        elif st.get("frozen"):
            df.freeze(st.get("reason") or "", by="process")
        else:
            # only clear if durable not emergency without auth - skip auto-clear
            pass
    except Exception:
        pass


# Patch methods
_orig_freeze = change_freeze.freeze
_orig_unfreeze = change_freeze.unfreeze
_orig_emergency = change_freeze.emergency
_orig_clear = change_freeze.clear_emergency

def _freeze(reason: str = "manual"):
    r = _orig_freeze(reason)
    _sync_durable_freeze()
    return r

def _unfreeze():
    r = _orig_unfreeze()
    try:
        from cintexa_platform.coordination import DurableFreeze
        DurableFreeze().unfreeze(by="process")
    except Exception:
        pass
    return r

def _emergency(reason: str = "emergency"):
    r = _orig_emergency(reason)
    _sync_durable_freeze()
    return r

def _clear_emergency(*, authorized: bool = False):
    r = _orig_clear(authorized=authorized)
    try:
        from cintexa_platform.coordination import DurableFreeze
        DurableFreeze().clear_emergency(authorized=authorized, by="process")
    except Exception:
        pass
    return r

change_freeze.freeze = _freeze
change_freeze.unfreeze = _unfreeze
change_freeze.emergency = _emergency
change_freeze.clear_emergency = _clear_emergency
