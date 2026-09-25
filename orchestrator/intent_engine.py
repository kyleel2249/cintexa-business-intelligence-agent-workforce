"""Intent understanding — extract structured goals from natural language."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from schemas.missions import AmbiguityLevel, Assumption, IntentModel, MissionPriority
# llm imported lazily in __init__

_DOMAIN_PATTERNS = [
    (r"\b(revenue|sales|churn|pipeline)\b", "revenue"),
    (r"\b(market|industry|segment|TAM|SAM)\b", "market"),
    (r"\b(competitor|competitive|rival)\b", "competitor"),
    (r"\b(forecast|predict|projection|next\s+\d+\s+month)\b", "forecast"),
    (r"\b(strateg(y|ic)|roadmap|growth plan)\b", "strategy"),
    (r"\b(decision|option|should we|trade-?off)\b", "decision"),
    (r"\b(diagnostic|health|assess|why.*(drop|decline|fall))\b", "diagnostic"),
    (r"\b(research|investigate|find out)\b", "research"),
]

_DELIVERABLE_PATTERNS = [
    (r"\breport\b", "report"),
    (r"\bforecast\b", "forecast"),
    (r"\bplan\b", "plan"),
    (r"\brecommend", "recommendations"),
    (r"\bstrateg", "strategy"),
    (r"\bdiagnos", "diagnostic"),
]

_AMBIGUOUS = re.compile(
    r"^(analyse|analyze|improve|fix|help|look at|check)\s+(our|my|the)?\s*(business|sales|company|performance)?\.?$",
    re.I,
)


class IntentEngine:
    def __init__(self) -> None:
        self._llm = None

    @property
    def llm(self):
        if self._llm is None:
            try:
                from tools.llm import get_llm
                self._llm = get_llm()
            except Exception:
                class _No:
                    def available(self, *a, **k): return False
                    def chat(self, *a, **k): return ""
                self._llm = _No()
        return self._llm

    def understand(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None,
    ) -> IntentModel:
        text = (text or "").strip()
        context = context or {}
        domain = self._detect_domain(text)
        deliverables = self._detect_deliverables(text)
        analysis = self._detect_analysis(text, domain)
        ambiguity = self._ambiguity(text)
        assumptions: List[Assumption] = []
        if ambiguity in (AmbiguityLevel.MEDIUM, AmbiguityLevel.HIGH, AmbiguityLevel.CRITICAL):
            assumptions.append(
                Assumption(
                    assumption="Proceed with available context; treat unspecified metrics as unavailable",
                    reason="Request lacks precise metrics or scope",
                    impact="medium",
                    requires_confirmation=ambiguity == AmbiguityLevel.CRITICAL,
                )
            )
        missing = []
        if domain in ("revenue", "forecast", "diagnostic") and "metrics" not in context:
            missing.append("historical_metrics")
        if domain == "competitor" and "competitors" not in context:
            missing.append("competitor_list")

        priority = MissionPriority.NORMAL
        if re.search(r"\b(urgent|asap|critical|immediately)\b", text, re.I):
            priority = MissionPriority.URGENT
        if re.search(r"\b(board|executive|investor)\b", text, re.I):
            priority = MissionPriority.HIGH

        intent = IntentModel(
            goal=text[:240],
            desired_outcome=self._desired_outcome(text, deliverables),
            business_domain=domain,
            requested_actions=analysis[:],
            requested_analysis=analysis,
            requested_deliverables=deliverables,
            constraints=list(context.get("constraints") or []),
            time_horizon=self._time_horizon(text),
            geography=context.get("geography"),
            priority=priority,
            known_data=list(context.keys()),
            missing_data=missing,
            implicit_tasks=analysis,
            ambiguity=ambiguity,
            assumptions=assumptions,
            raw_confidence=0.85 if ambiguity == AmbiguityLevel.NONE else 0.6,
        )

        # Optional LLM refinement when key available
        if self.llm.available(api_key) and len(text) > 20:
            refined = self._llm_refine(text, intent, api_key)
            if refined:
                return refined
        return intent

    def _detect_domain(self, text: str) -> str:
        for pattern, domain in _DOMAIN_PATTERNS:
            if re.search(pattern, text, re.I):
                return domain
        return "general"

    def _detect_deliverables(self, text: str) -> List[str]:
        out = []
        for pattern, name in _DELIVERABLE_PATTERNS:
            if re.search(pattern, text, re.I) and name not in out:
                out.append(name)
        if not out:
            out.append("analysis_summary")
        return out

    def _detect_analysis(self, text: str, domain: str) -> List[str]:
        base = {
            "revenue": [
                "historical_analysis",
                "driver_analysis",
                "customer_analysis",
                "product_analysis",
            ],
            "market": ["market_structure", "demand_drivers", "segment_analysis"],
            "competitor": ["competitor_profiling", "positioning_comparison"],
            "forecast": ["historical_series", "scenario_modelling", "uncertainty_bands"],
            "strategy": ["situation_analysis", "option_generation", "roadmap"],
            "decision": ["options_analysis", "risk_assessment", "tradeoffs"],
            "diagnostic": ["pillar_health", "gap_analysis", "priority_actions"],
            "research": ["source_collection", "evidence_grading"],
            "general": ["context_scan", "structured_analysis"],
        }
        items = list(base.get(domain, base["general"]))
        if re.search(r"\bwhy\b", text, re.I):
            items.insert(0, "root_cause_analysis")
        if re.search(r"\brecover|next quarter|what should we do\b", text, re.I):
            items.append("recovery_plan")
            items.append("action_plan")
        return items

    def _ambiguity(self, text: str) -> AmbiguityLevel:
        if len(text.split()) < 4 or _AMBIGUOUS.match(text.strip()):
            return AmbiguityLevel.HIGH
        if len(text.split()) < 8:
            return AmbiguityLevel.MEDIUM
        if re.search(r"\b(something|stuff|things|improve)\b", text, re.I):
            return AmbiguityLevel.MEDIUM
        return AmbiguityLevel.LOW

    def _time_horizon(self, text: str) -> Optional[str]:
        m = re.search(r"next\s+(\d+)\s+(month|quarter|year)s?", text, re.I)
        if m:
            return f"next_{m.group(1)}_{m.group(2)}s"
        if re.search(r"\bnext quarter\b", text, re.I):
            return "next_quarter"
        if re.search(r"\b12\s*month", text, re.I):
            return "12_months"
        return None

    def _desired_outcome(self, text: str, deliverables: List[str]) -> str:
        if "recovery_plan" in " ".join(deliverables) or re.search(r"recover|what should", text, re.I):
            return "Identify drivers and produce an actionable recovery plan"
        if "forecast" in deliverables:
            return "Produce a forecast with uncertainty and drivers"
        return "Produce a clear, evidence-aware analysis the user can act on"

    def _llm_refine(
        self, text: str, base: IntentModel, api_key: Optional[str]
    ) -> Optional[IntentModel]:
        try:
            prompt = (
                "Return JSON with keys: goal, desired_outcome, business_domain, "
                "requested_analysis (array), requested_deliverables (array), "
                "missing_data (array), ambiguity (NONE|LOW|MEDIUM|HIGH|CRITICAL).\n"
                f"Request: {text}"
            )
            raw = self.llm.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500,
                json_mode=True,
                api_key=api_key,
            )
            import json

            start, end = raw.find("{"), raw.rfind("}")
            if start < 0 or end <= start:
                return None
            data = json.loads(raw[start : end + 1])
            base.goal = data.get("goal") or base.goal
            base.desired_outcome = data.get("desired_outcome") or base.desired_outcome
            if data.get("business_domain"):
                base.business_domain = str(data["business_domain"])
            if isinstance(data.get("requested_analysis"), list):
                base.requested_analysis = [str(x) for x in data["requested_analysis"]]
            if isinstance(data.get("requested_deliverables"), list):
                base.requested_deliverables = [str(x) for x in data["requested_deliverables"]]
            if isinstance(data.get("missing_data"), list):
                base.missing_data = [str(x) for x in data["missing_data"]]
            amb = str(data.get("ambiguity") or "").upper()
            if amb in AmbiguityLevel.__members__:
                base.ambiguity = AmbiguityLevel[amb]
            return base
        except Exception:
            return None
