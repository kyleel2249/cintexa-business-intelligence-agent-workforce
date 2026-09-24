"""Research Agent — general research with source quality grading A–D."""

from datetime import date
from typing import Any, Dict, List

from agents.base import BaseAgent
from schemas.common import ConfidenceInfo, ConfidenceLevel, ConfidenceReason, SourceQuality
from schemas.evidence import Evidence


class ResearchAgent(BaseAgent):
    agent_id = "research"

    async def execute(self, task_id: str, context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        self.start_run(task_id, input_summary="General research")

        question = inputs.get("request") or inputs.get("research_question") or "unspecified"
        # In production this would call registered web_search / url_retrieve tools.
        # Here we provide the clean adapter path: if no tool results are injected,
        # we return structured "unavailable" rather than inventing findings.

        tool_results = inputs.get("tool_results") or context.get("user_context", {}).get("tool_results")

        evidence_list: List[Evidence] = []
        findings: Dict[str, Any] = {
            "question": question,
            "sub_questions": [],
            "trends": [],
            "opportunities": [],
            "risks": [],
            "products": [],
            "strengths": [],
            "weaknesses": [],
            "source_quality_summary": {},
        }
        sources: List[Dict[str, Any]] = []

        if tool_results and isinstance(tool_results, list):
            for item in tool_results:
                ev = Evidence(
                    claim=item.get("claim", ""),
                    source=item.get("url") or item.get("source", "unknown"),
                    source_type=item.get("source_type", "web"),
                    published_date=item.get("published_date"),
                    retrieved_date=date.today(),
                    confidence=float(item.get("confidence", 0.5)),
                    classification=item.get("classification", "PUBLICLY_REPORTED"),
                    source_quality=SourceQuality(item.get("quality", "C")),
                    supports=item.get("supports", []),
                )
                evidence_list.append(ev)
                sources.append({
                    "url": ev.source,
                    "quality": ev.source_quality.value,
                    "claim": ev.claim,
                })
                # Map into findings buckets if tagged
                for support in ev.supports:
                    if support in findings and isinstance(findings[support], list):
                        findings[support].append(ev.claim)
            findings["source_quality_summary"] = {
                "A": sum(1 for e in evidence_list if e.source_quality == SourceQuality.A),
                "B": sum(1 for e in evidence_list if e.source_quality == SourceQuality.B),
                "C": sum(1 for e in evidence_list if e.source_quality == SourceQuality.C),
                "D": sum(1 for e in evidence_list if e.source_quality == SourceQuality.D),
            }
            # D-level never treated as established fact
            findings["note"] = (
                "D-quality sources are listed for transparency but not treated as established fact."
            )
        else:
            findings["note"] = (
                "Research tools were not invoked or returned no results. "
                "No statistics, citations or findings have been invented. "
                "Connect a search adapter (Serper, Tavily, etc.) or supply tool_results."
            )

        evidence_ids = [e.evidence_id for e in evidence_list]

        result = {
            "status": "completed",
            "summary": (
                f"Research for: {question[:120]}. "
                f"Evidence items: {len(evidence_list)}."
            ),
            "findings": findings,
            "sources": sources,
            "evidence_ids": evidence_ids,
            "evidence": [e.model_dump() for e in evidence_list],
            "recommendations": [
                "Wire a web search adapter to enable live research; until then findings remain unavailable."
            ],
            "assumptions": [],
            "confidence": ConfidenceInfo(
                level=ConfidenceLevel.MEDIUM if evidence_list else ConfidenceLevel.LOW,
                reason=ConfidenceReason.EXTERNALLY_REPORTED if evidence_list else ConfidenceReason.MODEL_GENERATED,
            ).model_dump(),
        }
        self.finish_run(output_summary=result["summary"], evidence_ids=evidence_ids)
        return result
