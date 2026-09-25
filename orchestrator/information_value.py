"""Value of Information — decide whether to delay for missing data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class InfoGap:
    name: str
    potential_impact: str  # low|medium|high
    acquisition_cost: str  # low|medium|high
    decision_sensitivity: str  # low|medium|high
    action: str  # obtain | proceed_with_limitation | ask_user


class InformationValueEngine:
    def evaluate(self, missing: List[str]) -> List[InfoGap]:
        gaps = []
        high_value = {"historical_metrics", "sales_history", "customer_data", "revenue"}
        for name in missing or []:
            impact = "high" if any(h in name.lower() for h in high_value) else "medium"
            cost = "low" if "metric" in name.lower() else "medium"
            sensitivity = impact
            if impact == "high" and cost != "high":
                action = "obtain"
            elif impact == "low" and cost == "high":
                action = "proceed_with_limitation"
            else:
                action = "proceed_with_limitation"
            gaps.append(
                InfoGap(
                    name=name,
                    potential_impact=impact,
                    acquisition_cost=cost,
                    decision_sensitivity=sensitivity,
                    action=action,
                )
            )
        return gaps

    def should_block(self, gaps: List[InfoGap]) -> bool:
        return any(g.action == "obtain" and g.potential_impact == "high" for g in gaps)


information_value = InformationValueEngine()
