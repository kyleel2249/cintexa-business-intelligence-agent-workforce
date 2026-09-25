"""Final synthesis — separate facts, estimates, inferences, assumptions."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from schemas.missions import Mission, MissionResult, MissionStatus, MissionTaskStatus
# llm imported lazily


class SynthesisEngine:
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

    def synthesise(self, mission: Mission, api_key: Optional[str] = None) -> MissionResult:
        findings: List[Any] = []
        evidence: List[Any] = list(mission.evidence or [])
        actions: List[str] = list(mission.actions or [])
        limitations: List[str] = []
        confidences: List[float] = []

        for t in mission.tasks:
            if t.status != MissionTaskStatus.COMPLETED:
                if t.status == MissionTaskStatus.FAILED:
                    limitations.append(f"Task failed: {t.objective} — {'; '.join(t.errors)[:120]}")
                continue
            confidences.append(t.confidence)
            summary = None
            if isinstance(t.result, dict):
                summary = t.result.get("summary") or t.result.get("executive_summary")
                if t.result.get("recommendations"):
                    actions.extend([str(x) for x in t.result["recommendations"][:5]])
                if t.result.get("findings"):
                    findings.append({"agent": t.assigned_agent_id or t.role, "findings": t.result["findings"]})
                if t.result.get("evidence_ids"):
                    evidence.extend(
                        [{"id": eid, "task_id": t.task_id} for eid in t.result["evidence_ids"]]
                    )
            findings.append(
                {
                    "task_id": t.task_id,
                    "objective": t.objective,
                    "agent": t.assigned_agent_id or t.role,
                    "summary": summary or "Completed without narrative summary",
                    "confidence": t.confidence,
                    "category": "INFERENCE" if t.confidence < 0.7 else "KNOWN_FACT_OR_ANALYSIS",
                }
            )

        avg_conf = sum(confidences) / len(confidences) if confidences else 0.4
        completed = sum(1 for t in mission.tasks if t.status == MissionTaskStatus.COMPLETED)
        total = max(1, len(mission.tasks))
        quality = min(0.99, 0.5 * avg_conf + 0.5 * (completed / total))

        summary = f"Mission '{mission.normalized_objective.objective if mission.normalized_objective else mission.objective}' "
        summary += f"finished with {completed}/{total} tasks complete (confidence={avg_conf:.2f})."

        if self.llm.available(api_key):
            try:
                blob = {
                    "objective": mission.objective,
                    "findings": findings[:12],
                    "conflicts": [c.model_dump() for c in (mission.conflicts or [])][:5],
                    "assumptions": [a.model_dump() for a in (mission.intent.assumptions if mission.intent else [])],
                }
                text = self.llm.chat(
                    [
                        {
                            "role": "user",
                            "content": (
                                "Write a concise executive summary (British English) for this mission. "
                                "Separate what is known vs assumed. Do not invent metrics.\n"
                                + str(blob)[:6000]
                            ),
                        }
                    ],
                    temperature=0.2,
                    max_tokens=700,
                    api_key=api_key,
                )
                if text and len(text) > 40:
                    summary = text.strip()
            except Exception:
                pass

        if mission.missing_information:
            limitations.append("Missing information: " + ", ".join(mission.missing_information))
        for c in mission.conflicts or []:
            if c.resolution_status.value == "UNRESOLVED":
                limitations.append("Unresolved conflict: " + "; ".join(c.claims[:2]))

        trace_lines = [
            f"Mission {mission.mission_id} status={mission.status.value}",
            f"Plan v{mission.plan_version} team={mission.assigned_agents}",
        ]
        for t in mission.tasks:
            trace_lines.append(
                f"  - {t.task_id} [{t.status.value}] agent={t.assigned_agent_id or t.role} :: {t.objective}"
            )

        return MissionResult(
            mission_id=mission.mission_id,
            status=MissionStatus.COMPLETED,
            objective=mission.objective,
            summary=summary,
            findings=findings,
            evidence=evidence,
            assumptions=list(mission.intent.assumptions) if mission.intent else [],
            uncertainties=list(mission.missing_information or []),
            conflicts=list(mission.conflicts or []),
            decisions=list(mission.decisions or []),
            actions=actions[:20],
            confidence=avg_conf,
            quality=quality,
            limitations=limitations,
            execution_trace="\n".join(trace_lines),
            deliverables={
                "analysis_requirements": (
                    mission.normalized_objective.analysis_requirements
                    if mission.normalized_objective
                    else []
                ),
            },
        )
