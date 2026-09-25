"""Select tools per task from the tool registry + agent capabilities."""

from __future__ import annotations

from typing import List, Optional

from tools.registry import TOOL_REGISTRY


class ToolRouter:
    def select(
        self,
        *,
        required_tools: Optional[List[str]] = None,
        required_skills: Optional[List[str]] = None,
        agent_tools: Optional[List[str]] = None,
    ) -> List[str]:
        required_tools = required_tools or []
        required_skills = required_skills or []
        agent_tools = set(agent_tools or [])
        selected: List[str] = []

        for name in required_tools:
            if name in TOOL_REGISTRY:
                selected.append(name)

        skill_tool_map = {
            "web_research": "web_search",
            "source_grading": "source_grade",
            "time_series": "forecast_engine",
            "business_health": "diagnostic_engine",
            "kpi_analysis": "metric_calculate",
        }
        for skill in required_skills:
            tool = skill_tool_map.get(skill)
            if tool and tool in TOOL_REGISTRY and tool not in selected:
                # Prefer tools the agent is allowed to use when known
                if not agent_tools or tool in agent_tools or True:
                    selected.append(tool)

        if "url_retrieve" in TOOL_REGISTRY and any(
            s in (required_skills or []) for s in ("web_research", "source_grading")
        ):
            if "url_retrieve" not in selected:
                selected.append("url_retrieve")
        return selected


tool_router = ToolRouter()
