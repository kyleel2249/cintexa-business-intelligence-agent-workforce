"""Configurable execution policies for the Workforce Orchestrator."""

from dataclasses import dataclass, field
from typing import Dict, List, Set


@dataclass
class OrchestratorPolicies:
    max_concurrency: int = 4
    max_retries: int = 2
    max_task_depth: int = 24
    max_planning_iterations: int = 5
    max_replan_cycles: int = 3
    min_evidence_confidence: float = 0.55
    min_final_confidence: float = 0.6
    max_mission_duration_seconds: int = 600
    task_timeout_seconds: int = 120
    enable_challenger: bool = True
    enable_parallel: bool = True
    enable_human_approval: bool = True
    high_risk_operations: Set[str] = field(
        default_factory=lambda: {
            "financial_transaction",
            "external_communication",
            "production_deployment",
            "irreversible_action",
            "sensitive_data_access",
        }
    )
    approval_triggers: Set[str] = field(
        default_factory=lambda: {
            "financial_transaction",
            "external_communication",
            "high_risk_decision",
        }
    )
    retryable_failures: Set[str] = field(
        default_factory=lambda: {
            "TIMEOUT",
            "TOOL_FAILURE",
            "MODEL_FAILURE",
            "RESOURCE_FAILURE",
            "UNKNOWN_FAILURE",
        }
    )
    non_retryable_failures: Set[str] = field(
        default_factory=lambda: {
            "PERMISSION_FAILURE",
            "VALIDATION_FAILURE",
            "LOGIC_FAILURE",
            "DATA_FAILURE",
        }
    )
    model_fallback_chain: List[str] = field(
        default_factory=lambda: ["openrouter", "openai", "anthropic", "deterministic"]
    )
    domain_agent_map: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "diagnostic": ["diagnostic", "intelligence", "quality"],
            "market": ["market", "research", "quality"],
            "competitor": ["competitor", "research", "quality"],
            "forecast": ["forecasting", "intelligence", "quality"],
            "strategy": ["strategy", "decision", "quality"],
            "decision": ["decision", "strategy", "quality"],
            "research": ["research", "knowledge", "quality"],
            "revenue": ["diagnostic", "intelligence", "forecasting", "decision", "quality"],
            "general": ["intelligence", "research", "quality"],
        }
    )


DEFAULT_POLICIES = OrchestratorPolicies()
