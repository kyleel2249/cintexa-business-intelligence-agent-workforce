"""Agent capability registry for transparent selection scoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from agents.registry import AGENT_REGISTRY, list_agents


@dataclass
class AgentCapability:
    agent_id: str
    name: str
    description: str = ""
    roles: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)
    input_types: List[str] = field(default_factory=list)
    output_types: List[str] = field(default_factory=list)
    supported_tools: List[str] = field(default_factory=list)
    required_permissions: List[str] = field(default_factory=list)
    risk_level: str = "low"
    cost_profile: str = "medium"
    latency_profile: str = "medium"
    quality_history: float = 0.85
    success_rate: float = 0.9
    failure_rate: float = 0.1
    specialisation: str = ""
    availability: bool = True
    current_load: int = 0
    confidence_profile: float = 0.8


# Static enrichment layered on AGENT_REGISTRY
_ENRICHMENT: Dict[str, Dict] = {
    "orchestrator": {
        "roles": ["mission_lead", "coordinator"],
        "skills": ["planning", "routing", "synthesis"],
        "domains": ["all"],
    },
    "strategy": {
        "roles": ["strategist", "planner"],
        "skills": ["swot", "roadmap", "smart_goals", "strategic_analysis"],
        "domains": ["strategy", "growth", "planning"],
    },
    "intelligence": {
        "roles": ["analyst", "kpi_analyst"],
        "skills": ["kpi_analysis", "segmentation", "trend_analysis"],
        "domains": ["bi", "performance", "revenue"],
    },
    "diagnostic": {
        "roles": ["diagnostician", "health_auditor"],
        "skills": ["business_health", "pillar_scoring", "gap_analysis"],
        "domains": ["diagnostic", "operations", "revenue"],
    },
    "market": {
        "roles": ["market_analyst"],
        "skills": ["market_sizing", "demand_analysis", "industry_research"],
        "domains": ["market", "industry"],
    },
    "competitor": {
        "roles": ["competitor_analyst"],
        "skills": ["competitive_profiling", "positioning_analysis"],
        "domains": ["competitor", "market"],
    },
    "research": {
        "roles": ["researcher", "evidence_collector", "fact_checker"],
        "skills": ["web_research", "source_grading", "literature_review"],
        "domains": ["research", "general"],
    },
    "decision": {
        "roles": ["decision_analyst"],
        "skills": ["options_analysis", "risk_assessment", "tradeoff_analysis"],
        "domains": ["decision", "strategy"],
    },
    "forecasting": {
        "roles": ["forecaster"],
        "skills": ["time_series", "scenario_modelling", "uncertainty_bands"],
        "domains": ["forecast", "revenue", "planning"],
    },
    "knowledge": {
        "roles": ["knowledge_manager"],
        "skills": ["indexing", "retrieval", "versioning"],
        "domains": ["knowledge"],
    },
    "memory": {
        "roles": ["memory_keeper"],
        "skills": ["context_storage", "recall"],
        "domains": ["memory"],
    },
    "quality": {
        "roles": ["quality_reviewer", "challenger"],
        "skills": ["qa_gate", "evidence_check", "claim_validation"],
        "domains": ["quality", "all"],
    },
}


class CapabilityRegistry:
    def __init__(self) -> None:
        self._caps: Dict[str, AgentCapability] = {}
        self._load()

    def _load(self) -> None:
        for profile in list_agents():
            aid = profile.agent_id if hasattr(profile, "agent_id") else profile.get("agent_id")
            if not aid:
                continue
            data = profile.model_dump() if hasattr(profile, "model_dump") else dict(profile)
            extra = _ENRICHMENT.get(aid, {})
            self._caps[aid] = AgentCapability(
                agent_id=aid,
                name=data.get("name", aid),
                description=data.get("description", ""),
                roles=extra.get("roles", []),
                skills=extra.get("skills", list(data.get("capabilities", []) or [])),
                domains=extra.get("domains", []),
                supported_tools=list(data.get("tools_allowed", []) or []),
                specialisation=data.get("description", "")[:120],
            )

    def get(self, agent_id: str) -> Optional[AgentCapability]:
        return self._caps.get(agent_id)

    def all(self) -> List[AgentCapability]:
        return list(self._caps.values())

    def score(
        self,
        agent_id: str,
        *,
        required_skills: Optional[List[str]] = None,
        domain: Optional[str] = None,
        required_tools: Optional[List[str]] = None,
    ) -> float:
        cap = self._caps.get(agent_id)
        if not cap or not cap.availability:
            return 0.0
        required_skills = required_skills or []
        required_tools = required_tools or []
        skill_match = 0.0
        if required_skills:
            hits = sum(
                1
                for s in required_skills
                if s.lower() in " ".join(cap.skills).lower()
                or s.lower() in " ".join(cap.domains).lower()
                or s.lower() in cap.specialisation.lower()
            )
            skill_match = hits / max(1, len(required_skills))
        else:
            skill_match = 0.4
        domain_match = 1.0 if domain and domain in cap.domains else (0.5 if not domain else 0.2)
        if domain == "all" or "all" in cap.domains:
            domain_match = 1.0
        tool_match = 1.0
        if required_tools and cap.supported_tools:
            tool_hits = sum(1 for t in required_tools if t in cap.supported_tools)
            tool_match = 0.5 + 0.5 * (tool_hits / max(1, len(required_tools)))
        load_penalty = min(0.3, cap.current_load * 0.05)
        latency_penalty = 0.05 if cap.latency_profile == "high" else 0.0
        score = (
            0.3 * skill_match
            + 0.25 * domain_match
            + 0.15 * tool_match
            + 0.15 * cap.quality_history
            + 0.1 * cap.success_rate
            + 0.05 * cap.confidence_profile
            - load_penalty
            - latency_penalty
            - 0.05 * cap.failure_rate
        )
        return max(0.0, min(1.0, score))

    def rank(
        self,
        *,
        required_skills: Optional[List[str]] = None,
        domain: Optional[str] = None,
        required_tools: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> List[tuple]:
        exclude = set(exclude or [])
        scored = []
        for aid, cap in self._caps.items():
            if aid in exclude or aid == "orchestrator":
                continue
            s = self.score(
                aid,
                required_skills=required_skills,
                domain=domain,
                required_tools=required_tools,
            )
            scored.append((aid, s, cap))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def record_outcome(self, agent_id: str, success: bool) -> None:
        cap = self._caps.get(agent_id)
        if not cap:
            return
        # Exponential moving average
        alpha = 0.1
        cap.success_rate = (1 - alpha) * cap.success_rate + alpha * (1.0 if success else 0.0)
        cap.failure_rate = 1.0 - cap.success_rate
        if success:
            cap.quality_history = min(0.99, cap.quality_history + 0.01)
        else:
            cap.quality_history = max(0.4, cap.quality_history - 0.02)


capability_registry = CapabilityRegistry()
