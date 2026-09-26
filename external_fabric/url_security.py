"""URL validation, SSRF protection, scheme/domain policy."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import List, Optional, Set
from urllib.parse import urlparse, urljoin

from core.errors import ValidationError


class UrlSecurityError(ValidationError):
    code = "url_security_error"


BLOCKED_SCHEMES = {
    "javascript", "data", "file", "chrome", "about", "blob", "ws", "wss",
}
PRIVATE_HOSTS = {"localhost", "metadata.google.internal", "metadata"}


@dataclass
class UrlPolicy:
    allow_http: bool = False
    allowed_domains: Optional[Set[str]] = None
    blocked_domains: Optional[Set[str]] = None
    max_redirects: int = 5


def _is_private_ip(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        )
    except ValueError:
        return False


def validate_url(url: str, policy: Optional[UrlPolicy] = None) -> str:
    policy = policy or UrlPolicy()
    if not url or not isinstance(url, str):
        raise UrlSecurityError("URL required")
    url = url.strip()
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme in BLOCKED_SCHEMES or not scheme:
        raise UrlSecurityError(f"Blocked or missing scheme: {scheme or '(none)'}")
    if scheme == "http" and not policy.allow_http:
        raise UrlSecurityError("HTTP requires explicit policy approval")
    if scheme not in ("http", "https"):
        raise UrlSecurityError(f"Unsupported scheme: {scheme}")
    host = (parsed.hostname or "").lower()
    if not host:
        raise UrlSecurityError("Missing host")
    if host in PRIVATE_HOSTS or host.endswith(".local") or host.endswith(".internal"):
        raise UrlSecurityError(f"Private/metadata host blocked: {host}")
    if _is_private_ip(host):
        raise UrlSecurityError(f"Private IP blocked: {host}")
    # IPv6 literals in brackets already handled by hostname
    if policy.blocked_domains:
        for d in policy.blocked_domains:
            if host == d or host.endswith("." + d):
                raise UrlSecurityError(f"Domain blocked: {host}")
    if policy.allowed_domains is not None:
        ok = any(host == d or host.endswith("." + d) for d in policy.allowed_domains)
        if not ok:
            raise UrlSecurityError(f"Domain not allowlisted: {host}")
    return url


def validate_redirect_chain(urls: List[str], policy: Optional[UrlPolicy] = None) -> List[str]:
    policy = policy or UrlPolicy()
    if len(urls) > policy.max_redirects:
        raise UrlSecurityError("Redirect chain too long")
    out = []
    for u in urls:
        out.append(validate_url(u, policy))
    return out
