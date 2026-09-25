"""Skill catalog shared across agents for selection and planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Skill:
    skill_id: str
    name: str
    description: str
    domains: List[str]


SKILLS: Dict[str, Skill] = {
    s.skill_id: s
    for s in [
        Skill("trend_analysis", "Trend analysis", "Time-based performance trends", ["bi", "revenue"]),
        Skill("kpi_analysis", "KPI analysis", "Metric definition and evaluation", ["bi"]),
        Skill("segmentation", "Segmentation", "Customer/product segment views", ["bi", "market"]),
        Skill("business_health", "Business health", "Multi-pillar diagnostic scoring", ["diagnostic"]),
        Skill("pillar_scoring", "Pillar scoring", "Score individual health pillars", ["diagnostic"]),
        Skill("gap_analysis", "Gap analysis", "Identify priority gaps", ["diagnostic"]),
        Skill("market_sizing", "Market sizing", "Structure market and demand", ["market"]),
        Skill("demand_analysis", "Demand analysis", "Demand drivers and barriers", ["market"]),
        Skill("competitive_profiling", "Competitive profiling", "Evidence-based competitor profiles", ["competitor"]),
        Skill("positioning_analysis", "Positioning analysis", "Compare positioning", ["competitor"]),
        Skill("web_research", "Web research", "Collect and grade public sources", ["research"]),
        Skill("source_grading", "Source grading", "Grade source quality A–D", ["research"]),
        Skill("time_series", "Time series", "Prepare series for forecast", ["forecast"]),
        Skill("scenario_modelling", "Scenario modelling", "Forecast scenarios", ["forecast"]),
        Skill("uncertainty_bands", "Uncertainty bands", "Express forecast uncertainty", ["forecast"]),
        Skill("strategic_analysis", "Strategic analysis", "SWOT/options/strategy", ["strategy"]),
        Skill("roadmap", "Roadmap", "Prioritised roadmap", ["strategy"]),
        Skill("smart_goals", "SMART goals", "Actionable goals", ["strategy"]),
        Skill("options_analysis", "Options analysis", "Compare decision options", ["decision"]),
        Skill("risk_assessment", "Risk assessment", "Risks per option", ["decision"]),
        Skill("tradeoff_analysis", "Trade-off analysis", "Explicit trade-offs", ["decision"]),
        Skill("qa_gate", "QA gate", "Final quality verification", ["quality"]),
        Skill("evidence_check", "Evidence check", "Validate evidence sufficiency", ["quality"]),
        Skill("planning", "Planning", "Mission planning", ["all"]),
        Skill("synthesis", "Synthesis", "Combine specialist outputs", ["all"]),
    ]
}


class SkillRegistry:
    def get(self, skill_id: str) -> Optional[Skill]:
        return SKILLS.get(skill_id)

    def all(self) -> List[Skill]:
        return list(SKILLS.values())

    def for_domain(self, domain: str) -> List[Skill]:
        return [s for s in SKILLS.values() if domain in s.domains or "all" in s.domains]


skill_registry = SkillRegistry()
