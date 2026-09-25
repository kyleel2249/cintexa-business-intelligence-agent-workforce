"""Decompose normalized objectives into executable mission tasks."""

from __future__ import annotations

from typing import List, Optional

from schemas.missions import IntentModel, MissionTask, NormalizedObjective

# analysis requirement → task template
_TEMPLATES = {
    "historical_analysis": {
        "objective": "Analyse historical performance trends",
        "skills": ["trend_analysis", "kpi_analysis"],
        "agent_hint": "intelligence",
        "outputs": ["trend_summary", "growth_rates"],
        "priority": 0.9,
    },
    "driver_analysis": {
        "objective": "Identify primary performance drivers",
        "skills": ["driver_analysis", "segmentation"],
        "agent_hint": "intelligence",
        "outputs": ["driver_ranking"],
        "priority": 0.85,
        "deps_on": ["historical_analysis"],
    },
    "customer_analysis": {
        "objective": "Analyse customer / segment contribution",
        "skills": ["segmentation"],
        "agent_hint": "intelligence",
        "outputs": ["segment_view"],
        "priority": 0.75,
    },
    "product_analysis": {
        "objective": "Analyse product / category performance",
        "skills": ["kpi_analysis"],
        "agent_hint": "intelligence",
        "outputs": ["product_view"],
        "priority": 0.75,
    },
    "market_structure": {
        "objective": "Map market structure and demand drivers",
        "skills": ["market_sizing", "demand_analysis"],
        "agent_hint": "market",
        "outputs": ["market_brief"],
        "priority": 0.8,
    },
    "demand_drivers": {
        "objective": "Identify demand drivers and barriers",
        "skills": ["demand_analysis"],
        "agent_hint": "market",
        "outputs": ["demand_drivers"],
        "priority": 0.7,
    },
    "segment_analysis": {
        "objective": "Segment market / customers",
        "skills": ["segmentation"],
        "agent_hint": "market",
        "outputs": ["segments"],
        "priority": 0.7,
    },
    "competitor_profiling": {
        "objective": "Profile named competitors with evidence",
        "skills": ["competitive_profiling"],
        "agent_hint": "competitor",
        "outputs": ["competitor_profiles"],
        "priority": 0.85,
    },
    "positioning_comparison": {
        "objective": "Compare positioning across competitors",
        "skills": ["positioning_analysis"],
        "agent_hint": "competitor",
        "outputs": ["positioning_map"],
        "priority": 0.75,
        "deps_on": ["competitor_profiling"],
    },
    "historical_series": {
        "objective": "Prepare historical series for forecasting",
        "skills": ["time_series"],
        "agent_hint": "forecasting",
        "outputs": ["series_ready"],
        "priority": 0.8,
    },
    "scenario_modelling": {
        "objective": "Build forecast scenarios with uncertainty",
        "skills": ["scenario_modelling", "uncertainty_bands"],
        "agent_hint": "forecasting",
        "outputs": ["forecast_scenarios"],
        "priority": 0.85,
        "deps_on": ["historical_series"],
    },
    "uncertainty_bands": {
        "objective": "Quantify forecast uncertainty bands",
        "skills": ["uncertainty_bands"],
        "agent_hint": "forecasting",
        "outputs": ["bands"],
        "priority": 0.7,
        "deps_on": ["scenario_modelling"],
    },
    "situation_analysis": {
        "objective": "Situation analysis for strategy",
        "skills": ["strategic_analysis", "swot"],
        "agent_hint": "strategy",
        "outputs": ["situation"],
        "priority": 0.85,
    },
    "option_generation": {
        "objective": "Generate strategic options",
        "skills": ["strategic_analysis"],
        "agent_hint": "strategy",
        "outputs": ["options"],
        "priority": 0.8,
        "deps_on": ["situation_analysis"],
    },
    "roadmap": {
        "objective": "Build prioritised roadmap",
        "skills": ["roadmap", "smart_goals"],
        "agent_hint": "strategy",
        "outputs": ["roadmap"],
        "priority": 0.75,
        "deps_on": ["option_generation"],
    },
    "options_analysis": {
        "objective": "Analyse decision options and trade-offs",
        "skills": ["options_analysis", "tradeoff_analysis"],
        "agent_hint": "decision",
        "outputs": ["options_matrix"],
        "priority": 0.9,
    },
    "risk_assessment": {
        "objective": "Assess risks for each option",
        "skills": ["risk_assessment"],
        "agent_hint": "decision",
        "outputs": ["risks"],
        "priority": 0.8,
        "deps_on": ["options_analysis"],
    },
    "tradeoffs": {
        "objective": "Surface explicit trade-offs",
        "skills": ["tradeoff_analysis"],
        "agent_hint": "decision",
        "outputs": ["tradeoffs"],
        "priority": 0.75,
        "deps_on": ["options_analysis"],
    },
    "pillar_health": {
        "objective": "Score business health pillars",
        "skills": ["business_health", "pillar_scoring"],
        "agent_hint": "diagnostic",
        "outputs": ["pillar_scores"],
        "priority": 0.9,
    },
    "gap_analysis": {
        "objective": "Identify priority gaps",
        "skills": ["gap_analysis"],
        "agent_hint": "diagnostic",
        "outputs": ["gaps"],
        "priority": 0.8,
        "deps_on": ["pillar_health"],
    },
    "priority_actions": {
        "objective": "Recommend priority actions",
        "skills": ["gap_analysis"],
        "agent_hint": "diagnostic",
        "outputs": ["actions"],
        "priority": 0.75,
        "deps_on": ["gap_analysis"],
    },
    "source_collection": {
        "objective": "Collect and grade sources",
        "skills": ["web_research", "source_grading"],
        "agent_hint": "research",
        "outputs": ["sources"],
        "priority": 0.8,
    },
    "evidence_grading": {
        "objective": "Grade evidence quality",
        "skills": ["source_grading"],
        "agent_hint": "research",
        "outputs": ["graded_evidence"],
        "priority": 0.7,
        "deps_on": ["source_collection"],
    },
    "root_cause_analysis": {
        "objective": "Hypothesise and test root causes",
        "skills": ["driver_analysis", "business_health"],
        "agent_hint": "diagnostic",
        "outputs": ["hypotheses", "root_causes"],
        "priority": 0.95,
    },
    "recovery_plan": {
        "objective": "Draft recovery / action plan",
        "skills": ["roadmap", "options_analysis"],
        "agent_hint": "strategy",
        "outputs": ["recovery_plan"],
        "priority": 0.9,
    },
    "action_plan": {
        "objective": "Produce concrete next actions",
        "skills": ["smart_goals"],
        "agent_hint": "strategy",
        "outputs": ["actions"],
        "priority": 0.85,
        "deps_on": ["recovery_plan"],
    },
    "context_scan": {
        "objective": "Scan available context and structure the problem",
        "skills": ["kpi_analysis"],
        "agent_hint": "intelligence",
        "outputs": ["context_summary"],
        "priority": 0.7,
    },
    "structured_analysis": {
        "objective": "Produce structured analysis of the request",
        "skills": ["kpi_analysis", "strategic_analysis"],
        "agent_hint": "intelligence",
        "outputs": ["analysis"],
        "priority": 0.75,
    },
}


class TaskDecomposer:
    def decompose(
        self,
        objective: NormalizedObjective,
        intent: IntentModel,
    ) -> List[MissionTask]:
        reqs = list(objective.analysis_requirements) or list(intent.requested_analysis)
        if not reqs:
            reqs = ["context_scan", "structured_analysis"]

        key_to_task: dict = {}
        tasks: List[MissionTask] = []

        for key in reqs:
            tmpl = _TEMPLATES.get(key) or {
                "objective": key.replace("_", " ").title(),
                "skills": [key],
                "agent_hint": "intelligence",
                "outputs": [key],
                "priority": 0.6,
            }
            task = MissionTask(
                objective=tmpl["objective"],
                required_skills=list(tmpl.get("skills") or []),
                required_capabilities=[tmpl.get("agent_hint", "intelligence")],
                outputs=list(tmpl.get("outputs") or []),
                priority=float(tmpl.get("priority", 0.5)),
                evidence_requirements=["user_context"],
            )
            # stash agent hint on role field temporarily for router
            task.role = tmpl.get("agent_hint")
            key_to_task[key] = task
            tasks.append(task)

        # Wire deps by template
        for key, task in key_to_task.items():
            tmpl = _TEMPLATES.get(key) or {}
            for dep_key in tmpl.get("deps_on") or []:
                parent = key_to_task.get(dep_key)
                if parent:
                    task.dependencies.append(parent.task_id)

        # Always append QA gate at the end (depends on all non-qa tasks)
        qa = MissionTask(
            objective="Quality assurance gate on mission outputs",
            required_skills=["qa_gate", "evidence_check"],
            required_capabilities=["quality"],
            outputs=["qa_verdict"],
            priority=1.0,
            role="quality",
            evidence_requirements=["all_prior_outputs"],
        )
        for t in tasks:
            qa.dependencies.append(t.task_id)
        tasks.append(qa)
        return tasks
