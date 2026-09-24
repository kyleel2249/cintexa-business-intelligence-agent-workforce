"""Forecasting Agent — data-supported forecasts with mandatory uncertainty."""

from typing import Any, Dict, List, Optional

from agents.base import BaseAgent
from schemas.common import ConfidenceInfo, ConfidenceLevel, ConfidenceReason


class ForecastingAgent(BaseAgent):
    agent_id = "forecasting"

    async def execute(self, task_id: str, context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        self.start_run(task_id, input_summary="Forecast generation")

        series = (
            inputs.get("historical_series")
            or context.get("user_context", {}).get("historical_series")
            or context.get("user_context", {}).get("time_series")
            or {}
        )
        horizon = inputs.get("horizon_months") or context.get("user_context", {}).get("horizon_months") or 12
        metric_name = inputs.get("metric") or "revenue"

        if not series:
            # Try to pull from intelligence agent metrics
            intel = context.get("prior_results", {}).get("intelligence", {})
            metrics = intel.get("metrics") or intel.get("findings", {}).get("metrics") or []
            # Still no historical series → refuse to invent a forecast
            result = {
                "status": "completed",
                "summary": "Forecast unavailable — no historical time-series data supplied.",
                "findings": {
                    "forecast_period": f"next {horizon} months",
                    "methodology": "none — insufficient data",
                    "assumptions": [],
                    "historical_range": "unavailable",
                    "projected_range": "unavailable",
                    "uncertainty": "unavailable",
                    "limitations": [
                        "A forecast was not generated because historical data was not provided.",
                        "Never represent a forecast as guaranteed.",
                    ],
                },
                "recommendations": [
                    "Supply a historical numeric series (e.g. monthly revenue for 12+ periods)."
                ],
                "assumptions": [],
                "evidence_ids": [],
                "confidence": ConfidenceInfo(
                    level=ConfidenceLevel.UNKNOWN, reason=ConfidenceReason.MODEL_GENERATED
                ).model_dump(),
            }
            self.finish_run(output_summary=result["summary"])
            return result

        # Use the first series found
        name, points = next(iter(series.items())) if isinstance(series, dict) else (metric_name, series)
        try:
            nums = [float(p) for p in points]
        except (TypeError, ValueError):
            return self.unavailable("historical_series", "non-numeric values")

        if len(nums) < 3:
            result = {
                "status": "completed",
                "summary": "Forecast unavailable — fewer than 3 historical points.",
                "findings": {
                    "forecast_period": f"next {horizon} months",
                    "methodology": "none — insufficient history",
                    "limitations": ["Need at least 3 historical points for a simple trend projection."],
                },
                "recommendations": ["Provide a longer historical series."],
                "evidence_ids": [],
                "confidence": ConfidenceInfo(
                    level=ConfidenceLevel.LOW, reason=ConfidenceReason.USER_PROVIDED
                ).model_dump(),
            }
            self.finish_run(output_summary=result["summary"])
            return result

        # Simple linear trend (transparent methodology — not a black box)
        n = len(nums)
        x_mean = (n - 1) / 2
        y_mean = sum(nums) / n
        numer = sum((i - x_mean) * (nums[i] - y_mean) for i in range(n))
        denom = sum((i - x_mean) ** 2 for i in range(n)) or 1
        slope = numer / denom
        intercept = y_mean - slope * x_mean

        forecast_points = []
        for h in range(1, int(horizon) + 1):
            point = intercept + slope * (n - 1 + h)
            forecast_points.append(round(point, 2))

        # Uncertainty: ±1 standard deviation of residuals as a simple band
        residuals = [nums[i] - (intercept + slope * i) for i in range(n)]
        variance = sum(r ** 2 for r in residuals) / max(n - 2, 1)
        std = variance ** 0.5
        lower = [round(p - 1.96 * std, 2) for p in forecast_points]
        upper = [round(p + 1.96 * std, 2) for p in forecast_points]

        result = {
            "status": "completed",
            "summary": (
                f"Simple linear trend forecast for '{name}' over next {horizon} periods. "
                f"Point forecast end: {forecast_points[-1]}; 95% band approx [{lower[-1]}, {upper[-1]}]."
            ),
            "findings": {
                "metric": name,
                "forecast_period": f"next {horizon} periods",
                "methodology": "Ordinary least-squares linear trend on supplied historical points only.",
                "assumptions": [
                    "Past linear trend continues (strong assumption).",
                    "No structural breaks, seasonality or external shocks modelled.",
                    "Residuals treated as roughly normal for the illustrative uncertainty band.",
                ],
                "historical_range": {"min": min(nums), "max": max(nums), "n": n},
                "projected_point_forecast": forecast_points,
                "projected_range": {"lower_approx_95": lower, "upper_approx_95": upper},
                "uncertainty": f"Approximate 95% band using residual std ≈ {round(std, 2)}",
                "limitations": [
                    "This is not a production-grade forecasting model.",
                    "Seasonality, exogenous variables and regime changes are not included.",
                    "Never treat the forecast as guaranteed.",
                ],
            },
            "recommendations": [
                "Validate against a hold-out period and consider seasonal models when more data exists."
            ],
            "assumptions": [
                "Linear trend continuation",
                "Homoscedastic residuals for the band",
            ],
            "evidence_ids": [],
            "confidence": ConfidenceInfo(
                level=ConfidenceLevel.LOW,
                reason=ConfidenceReason.ESTIMATED,
                notes="Simple trend only; uncertainty is illustrative.",
            ).model_dump(),
        }
        self.finish_run(output_summary=result["summary"])
        return result
