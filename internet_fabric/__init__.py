"""Universal Internet Intelligence & Web Access Fabric.

Builds on external_fabric (URL security, browser, governor) and Knowledge Fabric.
Agents plan research → search → retrieve → extract evidence → verify → cite.
External content is always UNTRUSTED_EXTERNAL_CONTENT.
"""

from internet_fabric.orchestrator import InternetResearchOrchestrator
from internet_fabric.search import SearchFabric, SearchResult
from internet_fabric.sources import SourceRegistry, SourceQualityEngine
from internet_fabric.evidence import EvidenceFabric, ClaimVerifier
from internet_fabric.capabilities import INTERNET_CAPABILITIES

__all__ = [
    "InternetResearchOrchestrator",
    "SearchFabric",
    "SearchResult",
    "SourceRegistry",
    "SourceQualityEngine",
    "EvidenceFabric",
    "ClaimVerifier",
    "INTERNET_CAPABILITIES",
]
