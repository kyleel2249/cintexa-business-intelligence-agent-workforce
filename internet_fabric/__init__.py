"""Universal Internet Intelligence & Web Access Fabric."""

from internet_fabric.orchestrator import InternetResearchOrchestrator
from internet_fabric.search import SearchFabric
from internet_fabric.capabilities import list_capabilities, REGISTRY

__all__ = [
    "InternetResearchOrchestrator",
    "SearchFabric",
    "list_capabilities",
    "REGISTRY",
]
