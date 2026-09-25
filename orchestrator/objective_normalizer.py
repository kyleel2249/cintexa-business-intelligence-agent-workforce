"""Normalize intent into a structured objective."""

from __future__ import annotations

from schemas.missions import IntentModel, NormalizedObjective


class ObjectiveNormalizer:
    def normalize(self, intent: IntentModel, original: str) -> NormalizedObjective:
        objective = intent.goal or original[:200]
        # Tighten vague goals
        if intent.business_domain == "revenue" and "decline" in original.lower():
            objective = "Diagnose revenue decline"
        elif intent.business_domain == "diagnostic":
            objective = "Assess business health and priority gaps"
        elif intent.business_domain == "forecast":
            objective = "Produce forecast with uncertainty bands"
        elif intent.business_domain == "strategy":
            objective = "Produce strategic plan and prioritised actions"
        elif intent.business_domain == "competitor":
            objective = "Produce evidence-based competitor comparison"
        elif intent.business_domain == "market":
            objective = "Produce market intelligence brief"
        elif intent.business_domain == "decision":
            objective = "Compare options and surface trade-offs"

        success = list(intent.requested_deliverables) or ["structured_analysis"]
        success = [f"Deliver {d}" for d in success]
        success.append("Separate facts, estimates, inferences, and assumptions")
        success.append("Mark unavailable data explicitly")

        return NormalizedObjective(
            objective=objective,
            desired_outcome=intent.desired_outcome,
            time_horizon=intent.time_horizon,
            analysis_requirements=list(intent.requested_analysis),
            deliverables=list(intent.requested_deliverables),
            constraints=list(intent.constraints),
            success_criteria=success,
        )
