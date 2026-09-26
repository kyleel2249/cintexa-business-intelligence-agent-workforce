"""External Web, Browser, Media & Social Interaction Fabric."""

from external_fabric.url_security import validate_url, UrlSecurityError
from external_fabric.governor import InteractionGovernor, InteractionDecision
from external_fabric.browser import BrowserEngine, BrowserSession
from external_fabric.research import WebResearchEngine
from external_fabric.kill_switch import ExternalKillSwitch

__all__ = [
    "validate_url",
    "UrlSecurityError",
    "InteractionGovernor",
    "InteractionDecision",
    "BrowserEngine",
    "BrowserSession",
    "WebResearchEngine",
    "ExternalKillSwitch",
]
