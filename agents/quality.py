"""Quality Assurance Agent — final gate before user-facing output."""

from typing import Any, Dict, List

from agents.base import BaseAgent
from schemas.common import QAResult


class QualityAssuranceAgent(BaseAgent):
    agent_id = "quality"

    async def execute(
        self,
        task_id: str,
        context: Dict[str, Any],
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        self.start_run(task_id, input_summary="QA review of specialist outputs")

        prior = context.get("prior_results", {})
        reasons: List[str] = []
        checks_passed: List[str] = []
        checks_failed: List[str] = []

        # 1. Hallucination / fabrication signals
        for agent_id, result in prior.items():
            if not isinstance(result, dict):
                continue
            text_blob = str(result).lower()
            forbidden_phrases = [
                "i researched this",
                "i checked your competitors",
                "based on industry averages of",
                "according to recent studies showing",
            ]
            for phrase in forbidden_phrases:
                if phrase in text_blob and "evidence_ids" not in result:
                    reasons.append(
                        f"{agent_id}: possible unsupported claim pattern '{phrase}' without evidence_ids"
                    )
                    checks_failed.append("hallucination_detection")

        # 2. Evidence presence for research-heavy agents
        research_agents = {"market", "competitor", "research"}
        for agent_id in research_agents:
            if agent_id in prior:
                res = prior[agent_id]
                if isinstance(res, dict) and res.get("status") == "completed":
                    if not res.get("evidence_ids") and not res.get("sources"):
                        # Only fail if they claimed findings
                        if res.get("findings") or res.get("summary"):
                            reasons.append(
                                f"{agent_id}: completed with findings but no evidence_ids or sources attached"
                            )
                            checks_failed.append("source_accuracy")
                    else:
                        checks_passed.append(f"{agent_id}_sources")

        # 3. Forecast must carry uncertainty
        if "forecasting" in prior:
            fc = prior["forecasting"]
            if isinstance(fc, dict) and fc.get("status") == "completed":
                if "uncertainty" not in str(fc).lower() and "range" not in str(fc).lower():
                    reasons.append("forecasting: missing explicit uncertainty or projected range")
                    checks_failed.append("completeness")
                else:
                    checks_passed.append("forecast_uncertainty")

        # 4. Diagnostic must disclose methodology
        if "diagnostic" in prior:
            diag = prior["diagnostic"]
            if isinstance(diag, dict):
                findings = diag.get("findings", {})
                if findings and not findings.get("methodology"):
                    reasons.append("diagnostic: overall methodology not disclosed")
                    checks_failed.append("completeness")
                else:
                    checks_passed.append("diagnostic_methodology")

        # 5. No silent invention of numeric market stats
        for agent_id, result in prior.items():
            if not isinstance(result, dict):
                continue
            findings = result.get("findings") or result.get("summary") or ""
            if isinstance(findings, dict):
                findings = str(findings)
            # Very light heuristic: large round percentages without evidence
            if "%" in findings and not result.get("evidence_ids") and agent_id in research_agents:
                # Only warn, do not auto-fail — QA can still approve with note
                reasons.append(
                    f"{agent_id}: percentage claims present; verify evidence_ids cover them"
                )

        # 6. Failed agents should be disclosed
        failed = [aid for aid, r in prior.items() if isinstance(r, dict) and r.get("status") == "failed"]
        if failed:
            reasons.append(f"Incomplete sections from failed agents: {', '.join(failed)}")
            checks_failed.append("completeness")

        qa_result = QAResult.APPROVED
        if any(
            c in checks_failed
            for c in ("hallucination_detection", "source_accuracy")
        ):
            qa_result = QAResult.REVISION_REQUIRED

        # Soft failures (warnings) still allow approval but surface reasons
        if not reasons:
            reasons.append("All automated checks passed.")
            checks_passed.append("all_clear")

        output = {
            "status": "completed",
            "qa_result": qa_result.value,
            "reasons": reasons,
            "checks_passed": list(set(checks_passed)),
            "checks_failed": list(set(checks_failed)),
            "summary": f"QA: {qa_result.value}",
            "findings": {
                "qa_result": qa_result.value,
                "reasons": reasons,
            },
            "evidence_ids": [],
        }

        self.finish_run(
            status="COMPLETED",
            output_summary=output["summary"],
            qa_result=qa_result.value,
        )
        # Attach QA result to run record
        if self._run:
            self._run.qa_result = qa_result.value
        return output
