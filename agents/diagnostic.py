"""Business Diagnostic Agent — transparent multi-pillar health assessment."""

from typing import Any, Dict, List

from agents.base import BaseAgent
from schemas.common import ConfidenceInfo, ConfidenceLevel, ConfidenceReason
from schemas.diagnostics import (
    DEFAULT_PILLARS,
    BusinessHealthReport,
    PillarMetric,
    PillarScore,
)


class BusinessDiagnosticAgent(BaseAgent):
    agent_id = "diagnostic"

    async def execute(
        self,
        task_id: str,
        context: Dict[str, Any],
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        self.start_run(task_id, input_summary=inputs.get("request", "")[:200])

        org_id = context.get("organisation_id", "unknown")
        user_metrics = inputs.get("metrics", {}) or context.get("user_context", {}).get("metrics", {})
        user_answers = inputs.get("answers", {}) or context.get("user_context", {}).get("answers", {})

        pillars: List[PillarScore] = []
        strengths: List[str] = []
        weaknesses: List[str] = []
        missing: List[str] = []

        for pillar_name in DEFAULT_PILLARS:
            score_obj = self._score_pillar(pillar_name, user_metrics, user_answers)
            pillars.append(score_obj)
            if score_obj.score is not None and score_obj.score >= 75:
                strengths.append(f"{pillar_name}: relatively strong ({score_obj.score})")
            elif score_obj.score is not None and score_obj.score < 55:
                weaknesses.append(f"{pillar_name}: needs attention ({score_obj.score})")
            if score_obj.missing_information:
                missing.extend(score_obj.missing_information)

        report = BusinessHealthReport(
            organisation_id=org_id,
            pillars=pillars,
            strengths=strengths,
            weaknesses=weaknesses,
            missing_information=list(set(missing)),
            task_id=task_id,
        )
        report.compute_overall()

        # Priority areas = lowest scored pillars with data
        scored = [(p.pillar, p.score) for p in pillars if p.score is not None]
        scored.sort(key=lambda x: x[1])
        report.priority_areas = [name for name, _ in scored[:3]]

        report.recommended_actions = self._actions_from_gaps(report)

        result = {
            "status": "completed",
            "summary": (
                f"Business Health Score: {report.overall_score}/100"
                if report.overall_score is not None
                else "Business Health Score: unavailable (insufficient data)"
            ),
            "findings": report.model_dump(),
            "recommendations": report.recommended_actions,
            "risks": report.risks,
            "metrics": [
                {"name": "overall_health_score", "value": report.overall_score, "unit": "/100"}
            ],
            "assumptions": [
                "Pillars without supplied metrics are marked UNKNOWN and excluded from average."
            ],
            "evidence_ids": [],
            "confidence": ConfidenceInfo(
                level=ConfidenceLevel.MEDIUM if report.overall_score is not None else ConfidenceLevel.LOW,
                reason=ConfidenceReason.USER_PROVIDED
                if user_metrics or user_answers
                else ConfidenceReason.MODEL_GENERATED,
            ).model_dump(),
        }

        self.finish_run(
            status="COMPLETED",
            output_summary=result["summary"],
            evidence_ids=[],
        )
        return result

    def _score_pillar(
        self,
        pillar: str,
        metrics: Dict[str, Any],
        answers: Dict[str, Any],
    ) -> PillarScore:
        # Deterministic, transparent scoring based on available inputs only.
        # No invented numbers.
        key = pillar.lower()
        pillar_metrics: List[PillarMetric] = []
        observations: List[str] = []
        missing_info: List[str] = []
        score = None
        conf = ConfidenceInfo(level=ConfidenceLevel.UNKNOWN, reason=ConfidenceReason.MODEL_GENERATED)

        # Map common metric keys
        metric_keys = {
            "strategy": ["strategic_clarity", "goal_completion_rate"],
            "sales": ["revenue", "sales_growth", "win_rate", "pipeline_value"],
            "marketing": ["lead_volume", "cac", "marketing_roi", "conversion_rate"],
            "customers": ["nps", "churn_rate", "retention_rate", "customer_count"],
            "operations": ["fulfiliment_time", "error_rate", "capacity_utilisation"],
            "finance": ["gross_margin", "net_margin", "cash_runway", "burn_rate"],
            "technology": ["system_uptime", "tech_debt_score", "automation_coverage"],
            "automation": ["processes_automated", "automation_coverage"],
            "data": ["data_completeness", "data_quality_score"],
            "risk": ["open_risks", "compliance_score"],
        }

        relevant = metric_keys.get(key, [])
        found_values = []
        for mk in relevant:
            if mk in metrics and metrics[mk] is not None:
                val = metrics[mk]
                pillar_metrics.append(
                    PillarMetric(
                        name=mk,
                        value=float(val) if isinstance(val, (int, float)) else None,
                        source="user_provided",
                        calculation_method="direct",
                        confidence=ConfidenceInfo(
                            level=ConfidenceLevel.HIGH,
                            reason=ConfidenceReason.USER_PROVIDED,
                        ),
                        data_type="user_provided",
                    )
                )
                if isinstance(val, (int, float)):
                    found_values.append(float(val))

        # Simple normalised scoring when values exist (example heuristics only)
        if found_values:
            # Normalise crudely into 0-100 for demonstration; real deployments
            # should use configurable scoring functions per metric.
            avg = sum(found_values) / len(found_values)
            # Assume many business metrics are already percentages or ratios
            if avg <= 1.0:
                score = round(avg * 100, 1)
            elif avg <= 100:
                score = round(avg, 1)
            else:
                score = min(100.0, round(avg / 10, 1))  # very rough fallback
            conf = ConfidenceInfo(
                level=ConfidenceLevel.MEDIUM,
                reason=ConfidenceReason.USER_PROVIDED,
                notes="Score derived from user-supplied metrics only.",
            )
            observations.append(f"{len(found_values)} metric(s) available for {pillar}.")
        else:
            missing_info.append(f"No metrics supplied for pillar '{pillar}'.")
            observations.append("Insufficient data to score this pillar.")

        # Optional qualitative answers
        if key in answers:
            observations.append(f"User note: {answers[key]}")

        return PillarScore(
            pillar=pillar,
            score=score,
            confidence=conf,
            metrics=pillar_metrics,
            observations=observations,
            missing_information=missing_info,
            methodology=(
                "Score is the simple average of available numeric metrics for the pillar, "
                "normalised to 0–100 where possible. Pillars without data remain unscored."
            ),
        )

    def _actions_from_gaps(self, report: BusinessHealthReport) -> List[str]:
        actions = []
        for p in report.pillars:
            if p.score is not None and p.score < 55:
                actions.append(
                    f"Investigate and improve {p.pillar} (current score {p.score}). "
                    "Supply additional metrics for a more precise assessment."
                )
            if p.missing_information:
                actions.append(
                    f"Provide data for {p.pillar}: {', '.join(p.missing_information[:2])}"
                )
        if not actions:
            actions.append("Continue monitoring existing metrics and refresh diagnostic quarterly.")
        return actions[:8]
