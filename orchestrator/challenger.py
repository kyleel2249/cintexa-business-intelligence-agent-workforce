"""Challenger mechanism — alternative analysis for important conclusions."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class Challenger:
    async def challenge(
        self,
        primary: Dict[str, Any],
        *,
        agent_execute=None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Produce a structured challenge report against a primary result.
        If agent_execute is provided (async callable), run quality agent as challenger.
        """
        issues: List[str] = []
        summary = str(primary.get("summary") or "")
        conf = float(primary.get("confidence") or 0.5)
        if conf >= 0.9 and not primary.get("evidence_ids"):
            issues.append("High confidence without evidence IDs")
        if "unavailable" in summary.lower() and conf > 0.7:
            issues.append("Confidence may be overstated given unavailable data language")
        if not primary.get("limitations") and conf < 0.6:
            issues.append("Low confidence should list limitations")

        alt_explanations = [
            "Alternative driver not ruled out due to missing data",
            "Definition mismatch possible (e.g. revenue vs collections)",
        ]

        result = {
            "status": "completed",
            "role": "challenger",
            "issues": issues,
            "alternative_explanations": alt_explanations,
            "overconfidence_risk": conf > 0.85 and bool(issues),
            "summary": (
                "Challenger review: " + ("; ".join(issues) if issues else "No major issues flagged")
            ),
            "confidence": 0.6,
        }

        if agent_execute:
            try:
                qa = await agent_execute(
                    "challenge",
                    context or {},
                    {"request": "Challenge primary analysis", "primary": primary},
                )
                if isinstance(qa, dict):
                    result["qa_challenge"] = qa.get("summary") or qa.get("qa_result")
            except Exception as e:
                result["qa_challenge_error"] = str(e)[:200]
        return result


challenger = Challenger()
