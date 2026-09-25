"""Evidence sufficiency evaluation."""

from __future__ import annotations

from typing import Any, Dict, List

from schemas.missions import EvidenceSufficiency


class EvidenceGate:
    def evaluate(self, evidence: List[Dict[str, Any]], risk_level: str = "medium") -> EvidenceSufficiency:
        n = len(evidence)
        if n == 0:
            return EvidenceSufficiency.INSUFFICIENT
        # crude scoring from presence + confidence fields
        confs = [float(e.get("confidence", 0.5)) for e in evidence if isinstance(e, dict)]
        avg = sum(confs) / len(confs) if confs else 0.4
        if n >= 5 and avg >= 0.8:
            level = EvidenceSufficiency.VERY_STRONG
        elif n >= 3 and avg >= 0.7:
            level = EvidenceSufficiency.STRONG
        elif n >= 2 and avg >= 0.55:
            level = EvidenceSufficiency.ADEQUATE
        elif n >= 1:
            level = EvidenceSufficiency.LIMITED
        else:
            level = EvidenceSufficiency.INSUFFICIENT
        # raise bar for high risk
        if risk_level in ("high", "critical"):
            order = list(EvidenceSufficiency)
            idx = order.index(level)
            if idx > 0:
                level = order[max(0, idx - 1)]
        return level

    def accepts_for_downstream(
        self, sufficiency: EvidenceSufficiency, downstream_risk: str = "medium"
    ) -> bool:
        if downstream_risk in ("high", "critical"):
            return sufficiency in (
                EvidenceSufficiency.STRONG,
                EvidenceSufficiency.VERY_STRONG,
            )
        return sufficiency in (
            EvidenceSufficiency.ADEQUATE,
            EvidenceSufficiency.STRONG,
            EvidenceSufficiency.VERY_STRONG,
            EvidenceSufficiency.LIMITED,
        )
