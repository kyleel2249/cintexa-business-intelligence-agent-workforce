"""Agent Registry — single source of truth for the 12 BI agents."""

from typing import Any, Dict, List, Optional

from schemas.agents import AgentCapability, AgentProfile, AgentToolPermission


def _perm(tool: str, allowed: bool = True, conditional: bool = False, approval: bool = False) -> AgentToolPermission:
    return AgentToolPermission(
        tool_name=tool,
        allowed=allowed,
        conditional=conditional,
        requires_approval=approval,
    )


AGENT_REGISTRY: Dict[str, AgentProfile] = {
    "orchestrator": AgentProfile(
        agent_id="orchestrator",
        name="CINTEXA Business Intelligence Orchestrator",
        role="Manager of the Business Intelligence workforce",
        description=(
            "Understands user requests, identifies objectives, creates task plans, "
            "selects specialists, maintains state, resolves incomplete outputs, "
            "routes through QA and synthesises the final response."
        ),
        capabilities=[
            AgentCapability(name="request_understanding", description="Parse and classify business requests"),
            AgentCapability(name="task_planning", description="Break complex requests into ordered tasks"),
            AgentCapability(name="agent_selection", description="Choose specialists and tools"),
            AgentCapability(name="state_management", description="Track task lifecycle and handoffs"),
            AgentCapability(name="synthesis", description="Combine validated specialist outputs"),
        ],
        tools=["task_create", "task_update", "agent_invoke", "event_publish"],
        permissions=[
            _perm("agent_invocation", True),
            _perm("task_creation", True),
            _perm("task_cancellation", True),
            _perm("sensitive_data_access", conditional=True),
            _perm("external_publishing", approval=True),
        ],
        inputs=["user_request", "business_context", "prior_task_results"],
        outputs=["task_plan", "final_synthesised_response", "approval_requests"],
        dependencies=[],
        confidence_rules=["Never claim specialist work was performed unless specialists ran"],
        escalation_rules=["Escalate incomplete data to user or research agent"],
        validation_rules=["All specialist outputs must pass QA before synthesis"],
        memory_rules=["Store only operational traces and approved results"],
        audit_requirements=["Log every agent invocation and final synthesis"],
    ),
    "strategy": AgentProfile(
        agent_id="strategy",
        name="Executive Strategy Agent",
        role="Transform business objectives into structured strategic plans",
        description=(
            "Strategic planning, goal setting, business model analysis, growth planning, "
            "SWOT, PESTLE, Porter's Five Forces, value chain, SMART objectives, scenario planning."
        ),
        capabilities=[
            AgentCapability(name="strategic_planning", description="Build structured strategic plans"),
            AgentCapability(name="swot_analysis", description="SWOT as analytical structure"),
            AgentCapability(name="pestle_analysis", description="PESTLE external factors"),
            AgentCapability(name="porters_five_forces", description="Competitive intensity analysis"),
            AgentCapability(name="smart_goals", description="Specific, Measurable, Achievable, Relevant, Time-bound goals"),
            AgentCapability(name="scenario_planning", description="Alternative futures and contingencies"),
        ],
        tools=["knowledge_retrieve", "evidence_attach", "report_generate"],
        permissions=[
            _perm("knowledge_retrieve", True),
            _perm("evidence_attach", True),
            _perm("report_generate", True),
            _perm("web_search", conditional=True),
        ],
        inputs=["business_objectives", "diagnostic_results", "market_findings", "competitor_findings"],
        outputs=["strategic_plan", "smart_goals", "roadmap", "scenarios"],
        dependencies=["diagnostic", "market", "competitor", "intelligence"],
        confidence_rules=["Every recommendation must identify evidence or assumptions"],
        escalation_rules=["Request research when market or competitor data missing"],
        validation_rules=["Frameworks are analytical structures, not absolute truth"],
        memory_rules=["Persist only approved strategic plans"],
        audit_requirements=["Record assumptions and evidence IDs for every recommendation"],
    ),
    "intelligence": AgentProfile(
        agent_id="intelligence",
        name="Business Intelligence Agent",
        role="Transform raw business data into meaningful business intelligence",
        description=(
            "KPI analysis, trend analysis, correlation, segmentation, anomaly detection, "
            "performance reporting and metric interpretation."
        ),
        capabilities=[
            AgentCapability(name="kpi_analysis", description="Calculate and interpret KPIs"),
            AgentCapability(name="trend_analysis", description="Identify trends over time"),
            AgentCapability(name="segmentation", description="Customer / product / channel segments"),
            AgentCapability(name="anomaly_detection", description="Flag unusual patterns"),
            AgentCapability(name="dashboard_metrics", description="Prepare dashboard-ready metrics"),
        ],
        tools=["metric_calculate", "data_validate", "evidence_attach"],
        permissions=[
            _perm("company_database", True),
            _perm("metric_calculate", True),
            _perm("data_validate", True),
        ],
        inputs=["revenue", "expenses", "sales", "customers", "leads", "conversion", "crm", "spreadsheets"],
        outputs=["kpi_report", "trend_summary", "anomalies", "metric_cards"],
        dependencies=["memory", "knowledge"],
        confidence_rules=["Every metric must carry name, value, period, source, method, confidence"],
        escalation_rules=["Request missing data rather than inventing values"],
        validation_rules=["Calculations must be reproducible from source data"],
        memory_rules=["Store derived metrics with clear lineage"],
        audit_requirements=["Log calculation methods and source references"],
    ),
    "diagnostic": AgentProfile(
        agent_id="diagnostic",
        name="Business Diagnostic Agent",
        role="Assess the health and performance of a business",
        description=(
            "Evaluates Strategy, Sales, Marketing, Customers, Operations, Finance, "
            "Technology, Automation, Data and Risk. Produces transparent Business Health Score."
        ),
        capabilities=[
            AgentCapability(name="health_scoring", description="Transparent multi-pillar health score"),
            AgentCapability(name="gap_analysis", description="Identify performance gaps"),
            AgentCapability(name="priority_ranking", description="Rank improvement areas"),
        ],
        tools=["diagnostic_engine", "metric_calculate", "evidence_attach"],
        permissions=[
            _perm("diagnostic_engine", True),
            _perm("company_database", True),
            _perm("metric_calculate", True),
        ],
        inputs=["business_profile", "metrics", "user_answers", "prior_reports"],
        outputs=["business_health_report", "pillar_scores", "recommended_actions"],
        dependencies=["intelligence", "memory"],
        confidence_rules=["Distinguish measured / estimated / inferred / user-provided"],
        escalation_rules=["Flag pillars with insufficient data as UNKNOWN"],
        validation_rules=["Score methodology must be disclosed"],
        memory_rules=["Store diagnostic results with version and date"],
        audit_requirements=["Record every metric used in scoring"],
    ),
    "market": AgentProfile(
        agent_id="market",
        name="Market Intelligence Agent",
        role="Research the external market surrounding a business",
        description=(
            "Industry, segments, demand, trends, pricing, regulations, technology changes, "
            "opportunities, risks and geographic factors. Every external claim carries source metadata."
        ),
        capabilities=[
            AgentCapability(name="industry_analysis", description="Map industry structure and dynamics"),
            AgentCapability(name="trend_research", description="Identify current market trends"),
            AgentCapability(name="demand_analysis", description="Customer demand signals"),
            AgentCapability(name="regulatory_scan", description="Relevant regulations and changes"),
        ],
        tools=["web_search", "url_retrieve", "evidence_attach", "source_grade"],
        permissions=[
            _perm("web_search", True),
            _perm("url_retrieve", True),
            _perm("evidence_attach", True),
        ],
        inputs=["industry", "geography", "product_category", "research_questions"],
        outputs=["market_report", "trend_list", "opportunity_list", "risk_list"],
        dependencies=["research"],
        confidence_rules=["Never present old information as current; show conflicting sources"],
        escalation_rules=["Escalate when primary sources unavailable"],
        validation_rules=["Every claim must have source, retrieval date and classification"],
        memory_rules=["Cache research with expiration / review dates"],
        audit_requirements=["Log all search queries and retrieved URLs"],
    ),
    "competitor": AgentProfile(
        agent_id="competitor",
        name="Competitor Research Agent",
        role="Produce evidence-based competitor intelligence",
        description=(
            "Competitors, products, pricing, positioning, features, target markets, "
            "distribution, marketing presence, technology and publicly documented strengths/weaknesses. "
            "Labels: CONFIRMED, PUBLICLY_REPORTED, ESTIMATED, INFERRED, UNKNOWN."
        ),
        capabilities=[
            AgentCapability(name="competitor_profiling", description="Build evidence-backed profiles"),
            AgentCapability(name="feature_comparison", description="Descriptive feature matrices"),
            AgentCapability(name="pricing_research", description="Public pricing signals"),
        ],
        tools=["web_search", "url_retrieve", "evidence_attach", "source_grade"],
        permissions=[
            _perm("web_search", True),
            _perm("url_retrieve", True),
            _perm("evidence_attach", True),
        ],
        inputs=["competitor_names", "industry", "geography", "comparison_criteria"],
        outputs=["competitor_profiles", "comparison_matrix", "positioning_map"],
        dependencies=["research", "market"],
        confidence_rules=["Never invent private company information; never declare 'better' without explicit criterion"],
        escalation_rules=["Mark UNKNOWN when data cannot be confirmed"],
        validation_rules=["All claims must carry classification label"],
        memory_rules=["Version competitor profiles with retrieval dates"],
        audit_requirements=["Log every source used for competitor claims"],
    ),
    "research": AgentProfile(
        agent_id="research",
        name="Research Agent",
        role="Perform general research for other BI agents",
        description=(
            "Websites, official docs, government sources, academic papers, industry reports, "
            "company publications, reputable news, public datasets. Source quality A–D."
        ),
        capabilities=[
            AgentCapability(name="question_decomposition", description="Break questions into sub-questions"),
            AgentCapability(name="source_evaluation", description="Grade sources A–D"),
            AgentCapability(name="cross_checking", description="Resolve conflicting information"),
            AgentCapability(name="citation_attachment", description="Attach structured citations"),
        ],
        tools=["web_search", "url_retrieve", "source_grade", "evidence_attach"],
        permissions=[
            _perm("web_search", True),
            _perm("url_retrieve", True),
            _perm("company_database", True),
            _perm("financial_database", conditional=True),
            _perm("email", False),
            _perm("database_write", False),
            _perm("publishing", False),
        ],
        inputs=["research_question", "sub_questions", "constraints"],
        outputs=["structured_findings", "evidence_bundle", "source_list"],
        dependencies=[],
        confidence_rules=["D-level sources never treated as established fact"],
        escalation_rules=["Escalate when high-authority sources unavailable"],
        validation_rules=["Cross-check before finalising findings"],
        memory_rules=["Store research projects with full source trail"],
        audit_requirements=["Log queries, URLs, grades and extraction steps"],
    ),
    "decision": AgentProfile(
        agent_id="decision",
        name="Decision Support Agent",
        role="Help users understand decisions without making decisions for them",
        description=(
            "Identify decision, options, objectives, constraints, evidence, uncertainties, "
            "consequences and risks. Present considerations; never decide on behalf of the user."
        ),
        capabilities=[
            AgentCapability(name="option_framing", description="Structure options with pros/cons"),
            AgentCapability(name="risk_mapping", description="Surface risks and uncertainties"),
            AgentCapability(name="consequence_analysis", description="Compare potential outcomes"),
        ],
        tools=["evidence_attach", "knowledge_retrieve"],
        permissions=[
            _perm("evidence_attach", True),
            _perm("knowledge_retrieve", True),
        ],
        inputs=["decision_statement", "options", "objectives", "constraints", "evidence"],
        outputs=["decision_brief", "option_comparison", "information_gaps"],
        dependencies=["intelligence", "market", "competitor", "forecasting"],
        confidence_rules=["Never hide uncertainty or manufacture certainty"],
        escalation_rules=["Highlight information gaps explicitly"],
        validation_rules=["Every option must list advantages, disadvantages, costs, risks, assumptions, evidence"],
        memory_rules=["Store decision briefs with version"],
        audit_requirements=["Record evidence used for each option"],
    ),
    "forecasting": AgentProfile(
        agent_id="forecasting",
        name="Forecasting Agent",
        role="Create data-supported forecasts",
        description=(
            "Revenue, sales, demand, customers, expenses, cash flow, inventory, leads, "
            "conversion, marketing and operational metrics. Always includes uncertainty range."
        ),
        capabilities=[
            AgentCapability(name="trend_forecast", description="Trend and seasonality models"),
            AgentCapability(name="uncertainty_quantification", description="Ranges and confidence intervals"),
            AgentCapability(name="assumption_documentation", description="Explicit assumption lists"),
        ],
        tools=["forecast_engine", "data_validate", "metric_calculate"],
        permissions=[
            _perm("forecast_engine", True),
            _perm("company_database", True),
            _perm("metric_calculate", True),
        ],
        inputs=["historical_series", "forecast_horizon", "methodology_preference"],
        outputs=["forecast_report", "projected_range", "assumptions", "limitations"],
        dependencies=["intelligence"],
        confidence_rules=["Never represent a forecast as guaranteed"],
        escalation_rules=["Refuse to forecast when historical data quality is insufficient"],
        validation_rules=["Every forecast must include period, methodology, assumptions, range, uncertainty, limitations"],
        memory_rules=["Version forecasts with model parameters"],
        audit_requirements=["Log data window, model choice and validation metrics"],
    ),
    "knowledge": AgentProfile(
        agent_id="knowledge",
        name="Knowledge Manager Agent",
        role="Manage the organisation's structured knowledge",
        description=(
            "Indexing, classification, tagging, deduplication, source tracking, retrieval, "
            "version management and stale-information detection."
        ),
        capabilities=[
            AgentCapability(name="indexing", description="Index documents and records"),
            AgentCapability(name="retrieval", description="Permission-aware retrieval"),
            AgentCapability(name="versioning", description="Track versions and review dates"),
            AgentCapability(name="stale_detection", description="Flag outdated knowledge"),
        ],
        tools=["file_search", "document_store", "index_update", "knowledge_retrieve"],
        permissions=[
            _perm("file_search", True),
            _perm("document_storage", True),
            _perm("indexing", True),
            _perm("deletion", conditional=True, approval=True),
            _perm("external_publishing", False),
        ],
        inputs=["documents", "policies", "reports", "research", "approved_outputs"],
        outputs=["knowledge_items", "retrieval_results", "stale_alerts"],
        dependencies=["memory"],
        confidence_rules=["Every knowledge item must have source, dates, owner, category, confidence, version"],
        escalation_rules=["Request approval before deletion"],
        validation_rules=["Deduplicate and track source relationships"],
        memory_rules=["Never silently promote assumptions to permanent knowledge"],
        audit_requirements=["Log every create, update, retrieve and delete"],
    ),
    "memory": AgentProfile(
        agent_id="memory",
        name="Memory Agent",
        role="Manage contextual memory used by the BI workforce",
        description=(
            "Separates short-term, working, long-term business, user-provided and derived memory. "
            "Permission-aware, auditable, versioned, deletable, traceable and source-linked."
        ),
        capabilities=[
            AgentCapability(name="short_term", description="Current task context"),
            AgentCapability(name="working_memory", description="Multi-agent workflow context"),
            AgentCapability(name="long_term", description="Approved persistent business information"),
            AgentCapability(name="user_provided", description="Explicitly supplied by the user"),
            AgentCapability(name="derived", description="Calculated from available evidence"),
        ],
        tools=["memory_store", "memory_retrieve", "memory_delete"],
        permissions=[
            _perm("memory_store", True),
            _perm("memory_retrieve", True),
            _perm("memory_delete", conditional=True, approval=True),
        ],
        inputs=["task_context", "user_data", "derived_metrics", "approved_outputs"],
        outputs=["memory_items", "context_packages"],
        dependencies=[],
        confidence_rules=["Never mix memory categories; never convert assumptions into permanent memory silently"],
        escalation_rules=["Request approval for long-term writes of sensitive data"],
        validation_rules=["Every item must be source-linked and permission-aware"],
        memory_rules=["Support deletion and version history"],
        audit_requirements=["Log every memory operation with actor and reason"],
    ),
    "quality": AgentProfile(
        agent_id="quality",
        name="Quality Assurance Agent",
        role="Inspect every important BI output before it reaches the user",
        description=(
            "Validates factual accuracy, numerical accuracy, source accuracy, data freshness, "
            "logical consistency, completeness, hallucination detection, assumption marking, "
            "formatting and security. Returns APPROVED or REVISION_REQUIRED."
        ),
        capabilities=[
            AgentCapability(name="factual_check", description="Are claims supported by evidence?"),
            AgentCapability(name="numerical_check", description="Are calculations correct?"),
            AgentCapability(name="source_check", description="Do citations support statements?"),
            AgentCapability(name="freshness_check", description="Is information current enough?"),
            AgentCapability(name="hallucination_detection", description="Did an agent invent information?"),
            AgentCapability(name="assumption_detection", description="Were assumptions clearly marked?"),
        ],
        tools=["evidence_verify", "calculation_verify", "source_verify"],
        permissions=[
            _perm("evidence_verify", True),
            _perm("calculation_verify", True),
            _perm("source_verify", True),
        ],
        inputs=["agent_output", "evidence_bundle", "task_context"],
        outputs=["qa_result", "revision_reasons", "approved_output"],
        dependencies=[],
        confidence_rules=["Reject outputs that invent statistics, citations or competitor data"],
        escalation_rules=["Return REVISION_REQUIRED with structured reasons"],
        validation_rules=["Check security: no restricted information leakage"],
        memory_rules=["Log QA decisions for audit"],
        audit_requirements=["Record every check performed and outcome"],
    ),
}


def get_agent(agent_id: str) -> Optional[AgentProfile]:
    return AGENT_REGISTRY.get(agent_id)


def list_agents(enabled_only: bool = True) -> List[AgentProfile]:
    agents = list(AGENT_REGISTRY.values())
    if enabled_only:
        agents = [a for a in agents if a.enabled]
    return agents


def agent_ids() -> List[str]:
    return list(AGENT_REGISTRY.keys())


_AGENT_CLASS_MAP = {
    "strategy": ("agents.strategy", "ExecutiveStrategyAgent"),
    "intelligence": ("agents.intelligence", "BusinessIntelligenceAgent"),
    "diagnostic": ("agents.diagnostic", "BusinessDiagnosticAgent"),
    "market": ("agents.market", "MarketIntelligenceAgent"),
    "competitor": ("agents.competitor", "CompetitorResearchAgent"),
    "research": ("agents.research", "ResearchAgent"),
    "decision": ("agents.decision", "DecisionSupportAgent"),
    "forecasting": ("agents.forecasting", "ForecastingAgent"),
    "knowledge": ("agents.knowledge", "KnowledgeManagerAgent"),
    "memory": ("agents.memory", "MemoryAgent"),
    "quality": ("agents.quality", "QualityAssuranceAgent"),
}

_instances: Dict[str, Any] = {}


def get_agent_instance(agent_id: str) -> Any:
    """Lazy singleton agent instances for orchestration."""
    if agent_id in _instances:
        return _instances[agent_id]
    if agent_id not in _AGENT_CLASS_MAP:
        raise KeyError(f"No agent implementation for '{agent_id}'")
    import importlib

    module_path, class_name = _AGENT_CLASS_MAP[agent_id]
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    inst = cls()
    _instances[agent_id] = inst
    return inst
