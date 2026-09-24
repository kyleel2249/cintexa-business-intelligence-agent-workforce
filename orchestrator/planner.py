"""Task Planner — turns a high-level request into a structured TaskPlan."""

from typing import Dict, List, Tuple

from schemas.common import Priority
from schemas.tasks import TaskPlan


# Keyword → agent mapping for simple routing (extensible)
OBJECTIVE_MAP: Dict[str, Tuple[str, List[str], bool, bool]] = {
    # objective_key: (objective_name, agents, needs_web, needs_user_data)
    "business_health": (
        "business_health_assessment",
        ["diagnostic", "intelligence", "quality"],
        False,
        True,
    ),
    "market_analysis": (
        "market_analysis",
        ["market", "research", "quality"],
        True,
        False,
    ),
    "competitor_research": (
        "competitor_research",
        ["competitor", "research", "quality"],
        True,
        False,
    ),
    "sales_performance": (
        "sales_performance_analysis",
        ["intelligence", "diagnostic", "quality"],
        False,
        True,
    ),
    "revenue_forecast": (
        "revenue_forecast",
        ["intelligence", "forecasting", "quality"],
        False,
        True,
    ),
    "growth_strategy": (
        "business_growth_assessment",
        [
            "diagnostic",
            "market",
            "competitor",
            "intelligence",
            "forecasting",
            "strategy",
            "decision",
            "quality",
        ],
        True,
        True,
    ),
    "decision_support": (
        "decision_support",
        ["decision", "intelligence", "quality"],
        False,
        True,
    ),
    "industry_research": (
        "industry_opportunity_risk_research",
        ["market", "research", "competitor", "quality"],
        True,
        False,
    ),
    "executive_report": (
        "executive_report",
        ["intelligence", "diagnostic", "strategy", "quality"],
        False,
        True,
    ),
}


def _detect_objective(request: str) -> str:
    text = request.lower()
    if any(k in text for k in ["health", "diagnose", "diagnostic", "assess my business"]):
        return "business_health"
    if any(k in text for k in ["competitor", "competition", "rival"]):
        return "competitor_research"
    if any(k in text for k in ["market", "industry trend", "demand"]):
        return "market_analysis"
    if any(k in text for k in ["forecast", "predict", "next 12 months", "projection"]):
        return "revenue_forecast"
    if any(k in text for k in ["sales performance", "sales analysis", "conversion"]):
        return "sales_performance"
    if any(k in text for k in ["growth strategy", "strategic plan", "12-month", "growth plan"]):
        return "growth_strategy"
    if any(k in text for k in ["compare options", "decision", "should i", "which option"]):
        return "decision_support"
    if any(k in text for k in ["executive report", "board report", "management report"]):
        return "executive_report"
    if any(k in text for k in ["industry", "opportunities and risks", "research this industry"]):
        return "industry_research"
    # Default: comprehensive growth-style assessment
    return "growth_strategy"


def build_task_plan(request: str, priority: Priority = Priority.MEDIUM) -> TaskPlan:
    key = _detect_objective(request)
    objective, agents, needs_web, needs_data = OBJECTIVE_MAP[key]

    # Parallel groups for independent research
    parallel: List[List[str]] = []
    sequential: List[str] = []
    deps: Dict[str, List[str]] = {}

    if key == "growth_strategy":
        parallel = [["diagnostic", "market", "competitor"]]
        sequential = ["intelligence", "forecasting", "strategy", "decision", "quality"]
        deps = {
            "intelligence": ["diagnostic"],
            "forecasting": ["intelligence"],
            "strategy": ["diagnostic", "market", "competitor", "intelligence", "forecasting"],
            "decision": ["strategy"],
            "quality": ["decision", "strategy", "forecasting", "intelligence"],
        }
    elif key in ("market_analysis", "competitor_research", "industry_research"):
        sequential = agents
        deps = {agents[-1]: agents[:-1]} if len(agents) > 1 else {}
    else:
        sequential = agents
        if len(agents) > 1:
            deps = {agents[i]: [agents[i - 1]] for i in range(1, len(agents))}

    return TaskPlan(
        request=request,
        objective=objective,
        agents_required=agents,
        priority=priority,
        requires_web_research=needs_web,
        requires_user_data=needs_data,
        requires_human_approval=False,
        sequential_steps=sequential,
        parallel_groups=parallel,
        dependencies=deps,
        estimated_tools=["web_search"] if needs_web else [],
        missing_information=[],
    )
