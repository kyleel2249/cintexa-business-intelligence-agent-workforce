"""Hypothesis tracking for diagnostic / investigative missions."""

from __future__ import annotations

from typing import List

from schemas.missions import Hypothesis, HypothesisStatus, Mission


class HypothesisManager:
    def seed_from_objective(self, mission: Mission) -> List[Hypothesis]:
        text = (mission.original_request or mission.objective or "").lower()
        hyps: List[Hypothesis] = []
        if "churn" in text or "customer" in text:
            hyps.append(Hypothesis(statement="Customer churn is a primary driver", status=HypothesisStatus.PROPOSED))
        if "pric" in text:
            hyps.append(Hypothesis(statement="Pricing pressure is a primary driver", status=HypothesisStatus.PROPOSED))
        if "product" in text or "category" in text:
            hyps.append(Hypothesis(statement="Product/category mix is a primary driver", status=HypothesisStatus.PROPOSED))
        if "market" in text or "demand" in text:
            hyps.append(Hypothesis(statement="Market demand shift is a primary driver", status=HypothesisStatus.PROPOSED))
        if "decline" in text or "drop" in text or "fell" in text:
            if not hyps:
                hyps.extend(
                    [
                        Hypothesis(statement="Volume decline is a primary driver"),
                        Hypothesis(statement="Mix/pricing is a primary driver"),
                        Hypothesis(statement="External market pressure is a primary driver"),
                    ]
                )
        return hyps
