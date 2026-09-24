"""Decision Support Agent — informs, never decides."""

from typing import Any, Dict, List

from agents.base import BaseAgent
from schemas.common import ConfidenceInfo, ConfidenceLevel, ConfidenceReason


class DecisionSupportAgent(BaseAgent):
    agent_id = "decision"

    async def execute(self, task_id: str, context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        self.start_run(task_id, input_summary="Decision support")

        decision = inputs.get("decision") or inputs.get("request") or "unspecified decision"
        options = inputs.get("options") or context.get("user_context", {}).get("options") or []
        prior = context.get("prior_results", {})

        # Build option frames from prior strategy / forecast / market if present
        option_frames: List[Dict[str, Any]] = []
        if options:
            for opt in options:
                name = opt if isinstance(opt, str) else opt.get("name", "Option")
                option_frames.append({
                    "name": name,
                    "advantages": opt.get("advantages", []) if isinstance(opt, dict) else [],
                    "disadvantages": opt.get("disadvantages", []) if isinstance(opt, dict) else [],
                    "costs": opt.get("costs", ["Not quantified — data unavailable"]) if isinstance(opt, dict) else ["Not quantified"],
                    "risks": opt.get("risks", []) if isinstance(opt, dict) else [],
                    "assumptions": opt.get("assumptions", []) if isinstance(opt, dict) else [],
                    "evidence": opt.get("evidence", []) if isinstance(opt, dict) else [],
                })
        else:
            # Derive two generic considerations from strategy if available
            strategy = prior.get("strategy", {})
            if strategy.get("findings"):
                option_frames.append({
                    "name": "Option A — Focus on current strengths",
                    "advantages": strategy["findings"].get("swot", {}).get("strengths", [])[:3],
                    "disadvantages": ["May under-invest in emerging opportunities"],
                    "costs": ["Not quantified — supply cost data"],
                    "risks": strategy.get("risks", [])[:2],
                    "assumptions": ["Current strengths remain relevant over the planning horizon"],
                    "evidence": [],
                })
                option_frames.append({
                    "name": "Option B — Pursue identified opportunities",
                    "advantages": strategy.get("opportunities", [])[:3],
                    "disadvantages": strategy["findings"].get("swot", {}).get("weaknesses", [])[:2],
                    "costs": ["Not quantified — supply cost data"],
                    "risks": strategy.get("risks", [])[:2],
                    "assumptions": ["Opportunities are real and reachable with available resources"],
                    "evidence": [],
                })
            else:
                option_frames.append({
                    "name": "Insufficient context",
                    "advantages": [],
                    "disadvantages": ["No options or prior analysis supplied"],
                    "costs": [],
                    "risks": [],
                    "assumptions": [],
                    "evidence": [],
                })

        gaps = []
        if not options:
            gaps.append("Explicit options not provided by the user.")
        if not prior.get("forecasting"):
            gaps.append("No forecast available to compare financial consequences.")
        if not prior.get("market"):
            gaps.append("No market intelligence attached.")

        result = {
            "status": "completed",
            "summary": f"Decision considerations prepared for: {str(decision)[:120]}",
            "findings": {
                "decision": decision,
                "options": option_frames,
                "objectives": inputs.get("objectives", []),
                "constraints": inputs.get("constraints", []),
                "uncertainties": gaps,
                "information_gaps": gaps,
                "note": "This agent informs the decision. It does not make the decision on behalf of the user.",
            },
            "recommendations": [
                "Review each option's assumptions and evidence before choosing.",
                "Supply missing cost and constraint data for tighter comparison.",
            ],
            "assumptions": ["Option frames are derived only from supplied or prior-agent data."],
            "risks": [r for opt in option_frames for r in opt.get("risks", [])],
            "evidence_ids": [],
            "confidence": ConfidenceInfo(
                level=ConfidenceLevel.MEDIUM if option_frames else ConfidenceLevel.LOW,
                reason=ConfidenceReason.INFERRED,
            ).model_dump(),
        }
        self.finish_run(output_summary=result["summary"])
        return result
