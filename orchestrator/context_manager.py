"""Per-task context packaging — only relevant evidence and prior outputs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from schemas.missions import Mission, MissionTask


class ContextManager:
    def package(
        self,
        mission: Mission,
        task: MissionTask,
        prior_results: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ctx = {
            "organisation_id": mission.organisation_id,
            "workspace_id": mission.workspace_id,
            "user_id": mission.user_id,
            "mission_id": mission.mission_id,
            "user_context": dict(mission.available_context or {}),
            "constraints": list(mission.constraints or []),
            "assumptions": [
                a.model_dump() if hasattr(a, "model_dump") else a
                for a in (mission.intent.assumptions if mission.intent else [])
            ],
            "known_conflicts": [
                c.model_dump() if hasattr(c, "model_dump") else c
                for c in (mission.conflicts or [])[:5]
            ],
            "prior_results": prior_results or {},
        }
        # Flatten common keys agents expect at top-level inputs via user_context
        uc = ctx["user_context"]
        for key in ("metrics", "answers", "industry", "geography", "competitors", "historical_series"):
            if key in uc and key not in ctx:
                ctx[key] = uc[key]
        return ctx

    def package_inputs(self, mission: Mission, task: MissionTask, prior_results: Dict[str, Any]) -> Dict[str, Any]:
        uc = mission.available_context or {}
        return {
            "objective": task.objective,
            "request": mission.original_request or mission.objective,
            "metrics": uc.get("metrics") or {},
            "answers": uc.get("answers") or {},
            "industry": uc.get("industry"),
            "geography": uc.get("geography"),
            "competitors": uc.get("competitors"),
            "historical_series": uc.get("historical_series"),
            "prior_results": prior_results,
            "expected_outputs": list(task.outputs or []),
            "success_criteria": list(task.success_criteria or []),
        }

    def compress(self, text: str, max_chars: int = 4000) -> str:
        if not text or len(text) <= max_chars:
            return text or ""
        return text[: max_chars - 20] + "\n…[truncated]"
