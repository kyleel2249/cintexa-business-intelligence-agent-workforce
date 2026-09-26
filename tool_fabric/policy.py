"""Execution policies — org-scoped allow/deny rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse


@dataclass
class ExecutionPolicy:
    organisation_id: str
    allowed_tools: Set[str] = field(default_factory=set)
    denied_tools: Set[str] = field(default_factory=set)
    allowed_commands: Set[str] = field(default_factory=lambda: {"python", "python3", "node", "echo", "cat", "ls", "pwd", "git"})
    denied_commands: Set[str] = field(default_factory=lambda: {"rm", "rmdir", "mkfs", "dd", "sudo", "chmod", "chown", "reboot", "shutdown"})
    network_mode: str = "allowlist"  # deny|allowlist|allow
    allowed_domains: Set[str] = field(default_factory=lambda: {"example.com", "httpbin.org", "api.github.com"})
    max_timeout_sec: int = 30
    max_output_bytes: int = 500_000
    workspace_only: bool = True

    def tool_allowed(self, slug: str) -> bool:
        if slug in self.denied_tools:
            return False
        if self.allowed_tools and slug not in self.allowed_tools:
            return False
        return True

    def command_allowed(self, executable: str) -> bool:
        base = executable.split("/")[-1]
        if base in self.denied_commands:
            return False
        if self.allowed_commands and base not in self.allowed_commands:
            return False
        return True

    def domain_allowed(self, url: str) -> bool:
        if self.network_mode == "deny":
            return False
        if self.network_mode == "allow":
            return True
        host = (urlparse(url).hostname or "").lower()
        if not host:
            return False
        # block private/localhost
        if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1") or host.startswith("10.") or host.startswith("192.168.") or host.startswith("169.254."):
            return False
        return any(host == d or host.endswith("." + d) for d in self.allowed_domains)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "organisation_id": self.organisation_id,
            "allowed_tools": sorted(self.allowed_tools),
            "denied_tools": sorted(self.denied_tools),
            "network_mode": self.network_mode,
            "allowed_domains": sorted(self.allowed_domains),
            "max_timeout_sec": self.max_timeout_sec,
        }


def default_policy(organisation_id: str) -> ExecutionPolicy:
    return ExecutionPolicy(organisation_id=organisation_id)
