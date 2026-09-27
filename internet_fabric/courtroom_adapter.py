"""Adapter for Courtroom Verification Engine integration.

No Courtroom package exists in this repository. This adapter defines the
contract Internet research uses when a Courtroom engine is connected later.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol


class CourtroomEvidenceSink(Protocol):
    def accept_internet_evidence(
        self,
        case_id: str,
        organisation_id: str,
        research_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        ...


class NullCourtroomSink:
    """Default sink when Courtroom Engine is not installed."""

    def accept_internet_evidence(
        self,
        case_id: str,
        organisation_id: str,
        research_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "accepted": False,
            "reason": "COURTROOM_ENGINE_NOT_INSTALLED",
            "case_id": case_id,
            "research_id": research_result.get("research_id"),
            "evidence_count": len(research_result.get("evidence") or []),
            "note": "Internet Fabric can supply evidence when Courtroom is wired",
        }


def package_for_courtroom(research_result: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize research output into an evidence package for deliberation."""
    return {
        "package_type": "internet_research_evidence",
        "research_id": research_result.get("research_id"),
        "question": research_result.get("question"),
        "sources": research_result.get("sources") or [],
        "evidence": research_result.get("evidence") or [],
        "claims": research_result.get("claims") or [],
        "contradictions": research_result.get("contradictions") or [],
        "findings": research_result.get("findings") or [],
        "citations": research_result.get("citations") or [],
        "limitations": research_result.get("limitations") or [],
        "trust_policy": research_result.get("trust_policy", "UNTRUSTED_EXTERNAL_CONTENT"),
        "methodology": research_result.get("methodology"),
    }
