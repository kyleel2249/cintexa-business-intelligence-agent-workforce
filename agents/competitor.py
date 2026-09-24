"""Competitor Research Agent — evidence-based only, with classification labels."""

from typing import Any, Dict, List

from agents.base import BaseAgent
from schemas.common import Classification, ConfidenceInfo, ConfidenceLevel, ConfidenceReason


class CompetitorResearchAgent(BaseAgent):
    agent_id = "competitor"

    async def execute(self, task_id: str, context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        self.start_run(task_id, input_summary="Competitor research")

        competitor_names = (
            inputs.get("competitors")
            or context.get("user_context", {}).get("competitors")
            or []
        )
        research = context.get("prior_results", {}).get("research", {})

        profiles: List[Dict[str, Any]] = []
        evidence_ids: List[str] = []
        threats: List[str] = []

        if not competitor_names:
            note = (
                "No competitor names supplied. Competitor profiles are unavailable. "
                "Provide competitor names or domains to research."
            )
            profiles = []
        elif research.get("status") == "completed" and research.get("findings"):
            # Use research findings if present; still label carefully
            for name in competitor_names:
                profiles.append({
                    "name": name,
                    "products": research["findings"].get("products", ["UNKNOWN"]),
                    "pricing": "UNKNOWN",
                    "positioning": "UNKNOWN",
                    "strengths": research["findings"].get("strengths", []),
                    "weaknesses": research["findings"].get("weaknesses", []),
                    "classification": Classification.PUBLICLY_REPORTED.value,
                    "note": "Only publicly reported items included; private data never inferred as fact.",
                })
            evidence_ids = research.get("evidence_ids", [])
        else:
            for name in competitor_names:
                profiles.append({
                    "name": name,
                    "products": "UNKNOWN",
                    "pricing": "UNKNOWN",
                    "positioning": "UNKNOWN",
                    "strengths": [],
                    "weaknesses": [],
                    "classification": Classification.UNKNOWN.value,
                    "note": "Research not executed or returned no findings. No data invented.",
                })

        result = {
            "status": "completed",
            "summary": (
                f"Competitor research for {len(competitor_names)} named competitor(s). "
                f"Profiles with evidence: {len(evidence_ids)} evidence item(s)."
            ),
            "findings": {
                "profiles": profiles,
                "comparison_note": (
                    "Comparisons remain descriptive. No competitor is labelled 'better' "
                    "without an explicitly defined, evidence-based criterion."
                ),
                "threats": threats,
            },
            "recommendations": [
                "Supply competitor websites or reports, and enable research tools for CONFIRMED / PUBLICLY_REPORTED data."
            ],
            "assumptions": [],
            "evidence_ids": evidence_ids,
            "sources": research.get("sources", []),
            "confidence": ConfidenceInfo(
                level=ConfidenceLevel.MEDIUM if evidence_ids else ConfidenceLevel.LOW,
                reason=ConfidenceReason.EXTERNALLY_REPORTED if evidence_ids else ConfidenceReason.MODEL_GENERATED,
            ).model_dump(),
        }
        self.finish_run(output_summary=result["summary"], evidence_ids=evidence_ids)
        return result
