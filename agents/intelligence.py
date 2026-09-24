"""Business Intelligence Agent — KPIs, trends, anomalies from supplied data only."""

from typing import Any, Dict, List

from agents.base import BaseAgent
from schemas.common import ConfidenceInfo, ConfidenceLevel, ConfidenceReason


class BusinessIntelligenceAgent(BaseAgent):
    agent_id = "intelligence"

    async def execute(self, task_id: str, context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        self.start_run(task_id, input_summary="BI metric analysis")

        metrics_in = inputs.get("metrics") or context.get("user_context", {}).get("metrics", {}) or {}
        series = inputs.get("time_series") or context.get("user_context", {}).get("time_series", {}) or {}

        metric_cards: List[Dict[str, Any]] = []
        anomalies: List[str] = []
        trends: List[str] = []
        missing: List[str] = []

        if not metrics_in and not series:
            missing.append("No metrics or time-series data supplied by the user or prior agents.")
            result = {
                "status": "completed",
                "summary": "No business metrics available for analysis.",
                "findings": {"metrics": [], "trends": [], "anomalies": [], "missing": missing},
                "metrics": [],
                "recommendations": ["Upload or connect revenue, sales, customer and conversion data."],
                "assumptions": [],
                "evidence_ids": [],
                "confidence": ConfidenceInfo(
                    level=ConfidenceLevel.UNKNOWN, reason=ConfidenceReason.MODEL_GENERATED
                ).model_dump(),
            }
            self.finish_run(output_summary=result["summary"])
            return result

        for name, value in metrics_in.items():
            card = {
                "metric_name": name,
                "value": value,
                "period": metrics_in.get(f"{name}_period", "unspecified"),
                "source": "user_provided",
                "calculation_method": "direct",
                "confidence": ConfidenceInfo(
                    level=ConfidenceLevel.HIGH, reason=ConfidenceReason.USER_PROVIDED
                ).model_dump(),
                "interpretation": f"Value of {name} as supplied by the user.",
            }
            metric_cards.append(card)

        # Simple trend detection on series if present
        for series_name, points in series.items():
            if isinstance(points, list) and len(points) >= 2:
                try:
                    nums = [float(p) for p in points]
                    if nums[-1] > nums[0]:
                        trends.append(f"{series_name}: upward direction across supplied points")
                    elif nums[-1] < nums[0]:
                        trends.append(f"{series_name}: downward direction across supplied points")
                    else:
                        trends.append(f"{series_name}: flat across supplied points")
                    # Crude anomaly: last point > 2x median of prior
                    if len(nums) >= 3:
                        prior = sorted(nums[:-1])
                        median = prior[len(prior) // 2]
                        if median > 0 and nums[-1] > 2 * median:
                            anomalies.append(
                                f"{series_name}: latest value {nums[-1]} is more than 2× median of prior points"
                            )
                except (TypeError, ValueError):
                    missing.append(f"Could not parse numeric series for {series_name}")

        result = {
            "status": "completed",
            "summary": f"Analysed {len(metric_cards)} metric(s) and {len(series)} series.",
            "findings": {
                "metrics": metric_cards,
                "trends": trends,
                "anomalies": anomalies,
                "missing": missing,
            },
            "metrics": metric_cards,
            "recommendations": [
                "Refresh metrics regularly and attach source periods for each KPI."
            ],
            "assumptions": [
                "All values treated as user-provided; no external benchmarks applied."
            ],
            "evidence_ids": [],
            "confidence": ConfidenceInfo(
                level=ConfidenceLevel.HIGH, reason=ConfidenceReason.USER_PROVIDED
            ).model_dump(),
        }
        self.finish_run(output_summary=result["summary"])
        return result
