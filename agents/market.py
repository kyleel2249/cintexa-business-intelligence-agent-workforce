"""Market Intelligence Agent — external market research with mandatory evidence."""

from typing import Any, Dict, List

from agents.base import BaseAgent
from schemas.common import Classification, ConfidenceInfo, ConfidenceLevel, ConfidenceReason
from schemas.evidence import Evidence


class MarketIntelligenceAgent(BaseAgent):
    agent_id = "market"

    async def execute(self, task_id: str, context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        self.start_run(task_id, input_summary="Market intelligence research")

        industry = inputs.get("industry") or context.get("user_context", {}).get("industry")
        geography = inputs.get("geography") or context.get("user_context", {}).get("geography", "unspecified")

        # Tool adapter: web research is optional and must be explicitly invoked.
        # When no research tool result is present we mark findings unavailable.
        research_results = context.get("prior_results", {}).get("research", {})
        evidence_ids: List[str] = []
        findings: Dict[str, Any] = {
            "industry": industry or "not specified",
            "geography": geography,
            "trends": [],
            "segments": [],
            "opportunities": [],
            "risks": [],
            "regulations": [],
            "data_status": "unavailable",
        }

        if research_results.get("status") == "completed" and research_results.get("findings"):
            findings["trends"] = research_results["findings"].get("trends", [])
            findings["opportunities"] = research_results["findings"].get("opportunities", [])
            findings["risks"] = research_results["findings"].get("risks", [])
            findings["data_status"] = "from_research_agent"
            evidence_ids = research_results.get("evidence_ids", [])
        else:
            findings["note"] = (
                "No current external market data was retrieved. "
                "Market statistics, trend percentages and sizing figures are marked unavailable. "
                "Supply industry/geography and enable web research, or upload market reports."
            )
            findings["trends"] = ["Unavailable — research not executed or returned no findings"]
            findings["opportunities"] = ["Unavailable until evidence-backed research is completed"]
            findings["risks"] = ["Unavailable until evidence-backed research is completed"]

        result = {
            "status": "completed",
            "summary": (
                f"Market intelligence for industry='{industry or 'unspecified'}', "
                f"geography='{geography}'. Data status: {findings['data_status']}."
            ),
            "findings": findings,
            "opportunities": findings.get("opportunities", []),
            "risks": findings.get("risks", []),
            "recommendations": [
                "Enable web research or upload recent industry reports for evidence-backed market views."
            ],
            "assumptions": [
                "No market statistics are invented. Only evidence-linked claims are presented as findings."
            ],
            "evidence_ids": evidence_ids,
            "sources": research_results.get("sources", []),
            "confidence": ConfidenceInfo(
                level=ConfidenceLevel.MEDIUM if evidence_ids else ConfidenceLevel.LOW,
                reason=ConfidenceReason.EXTERNALLY_REPORTED if evidence_ids else ConfidenceReason.MODEL_GENERATED,
            ).model_dump(),
        }
        self.finish_run(output_summary=result["summary"], evidence_ids=evidence_ids)
        return result
