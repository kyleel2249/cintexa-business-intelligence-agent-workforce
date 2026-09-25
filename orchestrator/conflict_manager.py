"""Detect and resolve conflicts between agent claims."""

from __future__ import annotations

from typing import Any, Dict, List

from schemas.missions import Conflict, ConflictResolution


class ConflictManager:
    def detect(self, results: Dict[str, Dict[str, Any]]) -> List[Conflict]:
        """Heuristic: if multiple agents assert different 'primary_driver' style fields."""
        conflicts: List[Conflict] = []
        drivers = []
        for agent_id, result in results.items():
            if not isinstance(result, dict):
                continue
            for key in ("primary_driver", "root_cause", "main_finding", "summary"):
                val = result.get(key)
                if isinstance(val, str) and val.strip():
                    drivers.append((agent_id, key, val.strip()[:200]))
        # If two different primary drivers, flag
        primaries = [(a, v) for a, k, v in drivers if k in ("primary_driver", "root_cause")]
        if len(primaries) >= 2:
            claims = [f"{a}: {v}" for a, v in primaries]
            # distinct?
            vals = {v.lower() for _, v in primaries}
            if len(vals) > 1:
                conflicts.append(
                    Conflict(
                        claims=claims,
                        agents=[a for a, _ in primaries],
                        severity="medium",
                        resolution_status=ConflictResolution.UNRESOLVED,
                    )
                )
        return conflicts

    def resolve(self, conflict: Conflict) -> Conflict:
        # Without stronger evidence, mark partial / unresolved explicitly
        if len(conflict.claims) >= 2:
            conflict.resolution_status = ConflictResolution.BOTH_PARTIALLY_SUPPORTED
            conflict.resolution_notes = (
                "Multiple drivers reported; treat as complementary hypotheses pending stronger evidence."
            )
        return conflict
