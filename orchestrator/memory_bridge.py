"""Bridge workforce missions to the Memory Agent."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class MemoryBridge:
    async def recall(
        self,
        organisation_id: str,
        query: str,
        *,
        category: str = "working",
    ) -> List[Dict[str, Any]]:
        try:
            from agents.registry import get_agent_instance

            mem = get_agent_instance("memory")
            result = await mem.execute(
                "mem-recall",
                {"organisation_id": organisation_id},
                {"action": "retrieve", "category": category, "query": query},
            )
            if isinstance(result, dict):
                return list(result.get("items") or result.get("memories") or [])
        except Exception:
            return []
        return []

    async def store_decision(
        self,
        organisation_id: str,
        mission_id: str,
        decision: str,
    ) -> None:
        try:
            from agents.registry import get_agent_instance

            mem = get_agent_instance("memory")
            await mem.execute(
                "mem-store",
                {"organisation_id": organisation_id},
                {
                    "action": "store",
                    "category": "long_term",
                    "content": {"mission_id": mission_id, "decision": decision},
                },
            )
        except Exception:
            pass


memory_bridge = MemoryBridge()
