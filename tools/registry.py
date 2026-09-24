"""Tool registry and permission matrix for CINTEXA BI agents."""

from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field


class ToolDefinition(BaseModel):
    name: str
    description: str
    requires_approval: bool = False
    handler: Optional[str] = None  # import path or identifier


TOOL_REGISTRY: Dict[str, ToolDefinition] = {
    "web_search": ToolDefinition(
        name="web_search",
        description="Search the public web. Adapter required (Serper, Tavily, etc.).",
        requires_approval=False,
    ),
    "url_retrieve": ToolDefinition(
        name="url_retrieve",
        description="Fetch and extract text from a URL.",
        requires_approval=False,
    ),
    "source_grade": ToolDefinition(
        name="source_grade",
        description="Classify source quality A–D.",
    ),
    "evidence_attach": ToolDefinition(
        name="evidence_attach",
        description="Attach an evidence object to a claim.",
    ),
    "metric_calculate": ToolDefinition(
        name="metric_calculate",
        description="Calculate a metric from supplied data.",
    ),
    "data_validate": ToolDefinition(
        name="data_validate",
        description="Schema, type, missing-value and outlier checks.",
    ),
    "forecast_engine": ToolDefinition(
        name="forecast_engine",
        description="Run a forecasting method on historical series.",
    ),
    "diagnostic_engine": ToolDefinition(
        name="diagnostic_engine",
        description="Score configurable business health pillars.",
    ),
    "knowledge_retrieve": ToolDefinition(
        name="knowledge_retrieve",
        description="Permission-aware knowledge retrieval.",
    ),
    "file_search": ToolDefinition(
        name="file_search",
        description="Search organisation documents.",
    ),
    "document_store": ToolDefinition(
        name="document_store",
        description="Store a document in the knowledge base.",
    ),
    "index_update": ToolDefinition(
        name="index_update",
        description="Update search index for knowledge items.",
    ),
    "memory_store": ToolDefinition(
        name="memory_store",
        description="Store an item in a memory category.",
    ),
    "memory_retrieve": ToolDefinition(
        name="memory_retrieve",
        description="Retrieve memory items by category/query.",
    ),
    "memory_delete": ToolDefinition(
        name="memory_delete",
        description="Delete a memory item (may require approval).",
        requires_approval=True,
    ),
    "report_generate": ToolDefinition(
        name="report_generate",
        description="Generate a report in HTML/Markdown/PDF/DOCX/JSON.",
    ),
    "evidence_verify": ToolDefinition(
        name="evidence_verify",
        description="Verify evidence supports a claim.",
    ),
    "calculation_verify": ToolDefinition(
        name="calculation_verify",
        description="Recompute and verify numeric claims.",
    ),
    "source_verify": ToolDefinition(
        name="source_verify",
        description="Check citation accuracy and freshness.",
    ),
    "task_create": ToolDefinition(name="task_create", description="Create a task."),
    "task_update": ToolDefinition(name="task_update", description="Update task state."),
    "agent_invoke": ToolDefinition(name="agent_invoke", description="Invoke a specialist agent."),
    "event_publish": ToolDefinition(name="event_publish", description="Publish a domain event."),
    "company_database": ToolDefinition(
        name="company_database",
        description="Read organisation business data.",
    ),
    "financial_database": ToolDefinition(
        name="financial_database",
        description="Read financial records (conditional).",
    ),
}


def get_tool(name: str) -> Optional[ToolDefinition]:
    return TOOL_REGISTRY.get(name)


def list_tools() -> List[ToolDefinition]:
    return list(TOOL_REGISTRY.values())
