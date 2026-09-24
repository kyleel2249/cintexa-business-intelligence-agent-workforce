"""Memory Agent — separated short-term, working, long-term, user-provided, derived."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from agents.base import BaseAgent
from schemas.common import ConfidenceInfo, ConfidenceLevel, ConfidenceReason, new_id


MEMORY_CATEGORIES = (
    "short_term",
    "working",
    "long_term",
    "user_provided",
    "derived",
)


class MemoryAgent(BaseAgent):
    agent_id = "memory"

    def __init__(self):
        super().__init__()
        # organisation_id -> category -> list of items
        self._memory: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    async def execute(self, task_id: str, context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        self.start_run(task_id, input_summary="Memory operation")

        org_id = context.get("organisation_id", "default")
        action = inputs.get("action", "retrieve")  # store | retrieve | delete | package
        category = inputs.get("category", "working")

        if category not in MEMORY_CATEGORIES:
            return {
                "status": "failed",
                "error": f"Invalid memory category '{category}'. Must be one of {MEMORY_CATEGORIES}",
            }

        if action == "store":
            item = self._store(org_id, category, inputs, context)
            result = {
                "status": "completed",
                "summary": f"Stored {category} memory item {item['memory_id']}",
                "findings": {"item": item},
            }
        elif action == "delete":
            mid = inputs.get("memory_id")
            ok = self._delete(org_id, category, mid)
            result = {
                "status": "completed" if ok else "failed",
                "summary": f"Delete {'succeeded' if ok else 'failed'} for {mid}",
                "findings": {},
            }
        elif action == "package":
            package = self._package(org_id, task_id)
            result = {
                "status": "completed",
                "summary": "Context package assembled",
                "findings": {"package": package},
            }
        else:
            items = self._retrieve(org_id, category, inputs.get("query"))
            result = {
                "status": "completed",
                "summary": f"Retrieved {len(items)} {category} item(s)",
                "findings": {"items": items},
            }

        result["evidence_ids"] = []
        result["recommendations"] = []
        result["assumptions"] = []
        result["confidence"] = ConfidenceInfo(
            level=ConfidenceLevel.HIGH, reason=ConfidenceReason.USER_PROVIDED
        ).model_dump()
        self.finish_run(output_summary=result["summary"])
        return result

    def _ensure(self, org_id: str) -> None:
        if org_id not in self._memory:
            self._memory[org_id] = {c: [] for c in MEMORY_CATEGORIES}

    def _store(
        self,
        org_id: str,
        category: str,
        inputs: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        self._ensure(org_id)
        # Never silently promote assumptions into long_term
        if category == "long_term" and inputs.get("is_assumption"):
            raise ValueError("Assumptions cannot be stored as long-term memory without explicit approval")

        item = {
            "memory_id": new_id("MEM-"),
            "organisation_id": org_id,
            "category": category,
            "content": inputs.get("content"),
            "source": inputs.get("source", "agent"),
            "task_id": context.get("task_id"),
            "permissions": inputs.get("permissions", ["org_read"]),
            "version": 1,
            "created_at": datetime.utcnow().isoformat(),
            "source_linked": inputs.get("source_linked", True),
            "deletable": True,
        }
        self._memory[org_id][category].append(item)
        return item

    def _retrieve(self, org_id: str, category: str, query: Optional[str] = None) -> List[Dict[str, Any]]:
        self._ensure(org_id)
        items = self._memory[org_id][category]
        if not query:
            return list(items)
        q = query.lower()
        return [i for i in items if q in str(i.get("content", "")).lower()]

    def _delete(self, org_id: str, category: str, memory_id: Optional[str]) -> bool:
        self._ensure(org_id)
        before = len(self._memory[org_id][category])
        self._memory[org_id][category] = [
            i for i in self._memory[org_id][category] if i.get("memory_id") != memory_id
        ]
        return len(self._memory[org_id][category]) < before

    def _package(self, org_id: str, task_id: str) -> Dict[str, Any]:
        self._ensure(org_id)
        return {
            "task_id": task_id,
            "short_term": self._memory[org_id]["short_term"][-10:],
            "working": self._memory[org_id]["working"][-20:],
            "user_provided": self._memory[org_id]["user_provided"],
            "derived": self._memory[org_id]["derived"][-10:],
            # long_term only on explicit request / permission
        }
