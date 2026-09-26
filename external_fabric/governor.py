"""Interaction governor — anti-spam, budgets, cooldowns, decisions."""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from external_fabric.capabilities import get_capability
from external_fabric.kill_switch import ExternalKillSwitch


@dataclass
class InteractionDecision:
    decision: str  # ALLOW|ALLOW_WITH_COOLDOWN|REQUIRE_APPROVAL|DEFER|REJECT|BLOCK
    reason: str
    risk: str = "LOW"
    cooldown_sec: float = 0.0
    details: dict = field(default_factory=dict)


class InteractionGovernor:
    def __init__(self):
        self._action_times: Dict[str, List[float]] = {}
        self._content_hashes: Dict[str, float] = {}
        self._target_hits: Dict[str, float] = {}
        self.kill = ExternalKillSwitch()
        # limits
        self.limits = {
            "SOCIAL_LIKE": (30, 3600),
            "SOCIAL_COMMENT": (10, 3600),
            "SOCIAL_REPLY": (10, 3600),
            "SOCIAL_FOLLOW": (20, 3600),
            "SOCIAL_MESSAGE": (5, 3600),
            "WEB_SUBMIT_FORM": (10, 3600),
            "page_request": (60, 60),
        }

    def evaluate(
        self,
        *,
        organisation_id: str,
        capability_id: str,
        target: str = "",
        content: str = "",
        agent_id: str = "",
        account_id: str = "",
        permissions: Optional[Set[str]] = None,
        budget_remaining: Optional[int] = None,
    ) -> InteractionDecision:
        if self.kill.writes_blocked(organisation_id):
            return InteractionDecision("BLOCK", "EXTERNAL_WRITE_KILL_SWITCH", "CRITICAL")

        cap = get_capability(capability_id)
        if not cap:
            return InteractionDecision("REJECT", "UNKNOWN_CAPABILITY", "HIGH")

        perms = permissions or set()
        for p in cap.required_permissions:
            if p not in perms and "*" not in perms:
                return InteractionDecision("REJECT", "PERMISSION_MISSING", cap.risk_level, details={"perm": p})

        if budget_remaining is not None and budget_remaining <= 0:
            return InteractionDecision("BLOCK", "BUDGET_EXCEEDED", cap.risk_level)

        # rate limit
        key = f"{organisation_id}:{account_id or agent_id}:{capability_id}"
        max_n, window = self.limits.get(capability_id, (100, 3600))
        now = time.time()
        arr = [t for t in self._action_times.get(key, []) if now - t < window]
        if len(arr) >= max_n:
            return InteractionDecision("BLOCK", "RATE_LIMIT", cap.risk_level, details={"limit": max_n})
        self._action_times[key] = arr

        # page request global-ish
        if capability_id.startswith("WEB_") and cap.risk_level == "READ":
            pk = f"{organisation_id}:page_request"
            pr = [t for t in self._action_times.get(pk, []) if now - t < 60]
            if len(pr) >= 60:
                return InteractionDecision("BLOCK", "RATE_LIMIT", "READ")
            self._action_times[pk] = pr + [now]

        # duplicate content
        if content and capability_id in ("SOCIAL_COMMENT", "SOCIAL_REPLY", "SOCIAL_MESSAGE", "CONTENT_PUBLICATION"):
            norm = re.sub(r"\s+", " ", content.strip().lower())
            h = hashlib.sha256(norm.encode()).hexdigest()
            ck = f"{organisation_id}:{account_id}:{h}"
            prev = self._content_hashes.get(ck)
            if prev and now - prev < 86400:
                return InteractionDecision("BLOCK", "DUPLICATE_CONTENT", cap.risk_level)
            # near-duplicate against target
            tk = f"{organisation_id}:{target}:{h}"
            if self._content_hashes.get(tk) and now - self._content_hashes[tk] < 86400:
                return InteractionDecision("BLOCK", "DUPLICATE_CONTENT", cap.risk_level)

        # cooldown same target
        if target and capability_id.startswith("SOCIAL_"):
            tk = f"{organisation_id}:{account_id}:{capability_id}:{target}"
            last = self._target_hits.get(tk)
            if last and now - last < 300:
                return InteractionDecision(
                    "ALLOW_WITH_COOLDOWN" if cap.risk_level == "LOW" else "DEFER",
                    "TARGET_ALREADY_CONTACTED",
                    cap.risk_level,
                    cooldown_sec=300 - (now - last),
                )

        if cap.requires_approval or cap.risk_level in ("HIGH", "CRITICAL"):
            return InteractionDecision("REQUIRE_APPROVAL", "POLICY_REQUIRES_APPROVAL", cap.risk_level)

        # record intent (actual record_action called on success)
        return InteractionDecision("ALLOW", "OK", cap.risk_level)

    def record_action(
        self,
        *,
        organisation_id: str,
        capability_id: str,
        target: str = "",
        content: str = "",
        agent_id: str = "",
        account_id: str = "",
    ) -> None:
        now = time.time()
        key = f"{organisation_id}:{account_id or agent_id}:{capability_id}"
        self._action_times.setdefault(key, []).append(now)
        if content:
            norm = re.sub(r"\s+", " ", content.strip().lower())
            h = hashlib.sha256(norm.encode()).hexdigest()
            self._content_hashes[f"{organisation_id}:{account_id}:{h}"] = now
            if target:
                self._content_hashes[f"{organisation_id}:{target}:{h}"] = now
        if target:
            self._target_hits[f"{organisation_id}:{account_id}:{capability_id}:{target}"] = now
