"""Executive Strategy Agent."""

from typing import Any, Dict, List

from agents.base import BaseAgent
from schemas.common import ConfidenceInfo, ConfidenceLevel, ConfidenceReason


class ExecutiveStrategyAgent(BaseAgent):
    agent_id = "strategy"

    async def execute(self, task_id: str, context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        self.start_run(task_id, input_summary=inputs.get("request", "")[:200])
        prior = context.get("prior_results", {})

        diagnostic = prior.get("diagnostic", {})
        market = prior.get("market", {})
        competitor = prior.get("competitor", {})
        forecast = prior.get("forecasting", {})
        intelligence = prior.get("intelligence", {})

        strengths = []
        weaknesses = []
        opportunities = []
        threats = []
        assumptions = []
        recommendations = []
        smart_goals = []

        # Pull from diagnostic if available
        if isinstance(diagnostic.get("findings"), dict):
            d = diagnostic["findings"]
            strengths.extend(d.get("strengths", []))
            weaknesses.extend(d.get("weaknesses", []))
            opportunities.extend(d.get("opportunities", []))
            threats.extend(d.get("risks", []))

        if isinstance(market.get("findings"), dict):
            opportunities.extend(market["findings"].get("opportunities", []))
            threats.extend(market["findings"].get("risks", []))

        if isinstance(competitor.get("findings"), dict):
            threats.extend(competitor["findings"].get("threats", []))

        # SWOT as analytical structure (not absolute truth)
        swot = {
            "strengths": strengths or ["Insufficient data — supply business metrics for strength identification"],
            "weaknesses": weaknesses or ["Insufficient data — supply business metrics for weakness identification"],
            "opportunities": opportunities or ["Market opportunities marked unavailable until research completes"],
            "threats": threats or ["Competitive / market threats marked unavailable until research completes"],
        }

        # SMART goals example structure — only when enough context
        if diagnostic.get("status") == "completed":
            smart_goals.append({
                "specific": "Improve lowest-scoring business health pillar",
                "measurable": "Raise the lowest pillar score by at least 10 points",
                "achievable": "Based on current diagnostic gaps and available resources (assumption)",
                "relevant": "Supports overall business health and growth objective",
                "time_bound": "Within 90 days",
                "assumptions": ["User will supply missing metrics and prioritise the pillar"],
            })
            assumptions.append("SMART goal achievability depends on unobserved resource constraints.")

        recommendations.append(
            "Treat SWOT and frameworks as analytical lenses, not prescriptions."
        )
        if weaknesses:
            recommendations.append(
                f"Prioritise improvement of: {', '.join(weaknesses[:3])}."
            )
        if not strengths and not weaknesses:
            recommendations.append(
                "Run a full Business Diagnostic with metrics before locking strategic priorities."
            )

        result = {
            "status": "completed",
            "summary": "Strategic analysis assembled from available diagnostic, market and competitor inputs.",
            "findings": {
                "swot": swot,
                "smart_goals": smart_goals,
                "frameworks_used": ["SWOT", "SMART"],
                "note": "Frameworks are analytical structures only.",
            },
            "recommendations": recommendations,
            "assumptions": assumptions,
            "risks": threats,
            "opportunities": opportunities,
            "evidence_ids": [],
            "confidence": ConfidenceInfo(
                level=ConfidenceLevel.MEDIUM if strengths or weaknesses else ConfidenceLevel.LOW,
                reason=ConfidenceReason.INFERRED,
            ).model_dump(),
        }
        self.finish_run(output_summary=result["summary"])
        return result
