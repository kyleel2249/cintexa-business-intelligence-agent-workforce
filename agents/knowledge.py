"""Knowledge Manager Agent — structured knowledge with versioning and stale detection."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agents.base import BaseAgent
from schemas.common import ConfidenceInfo, ConfidenceLevel, ConfidenceReason, new_id


class KnowledgeManagerAgent(BaseAgent):
    agent_id = "knowledge"

    def __init__(self):
        super().__init__()
        # In-memory store for demo; production uses database.knowledge_items
        self._store: Dict[str, Dict[str, Any]] = {}

    async def execute(self, task_id: str, context: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
        self.start_run(task_id, input_summary="Knowledge management")

        action = inputs.get("action", "retrieve")  # index | retrieve | list | flag_stale
        org_id = context.get("organisation_id", "default")

        if action == "index":
            item = self._index(org_id, inputs)
            result = {
                "status": "completed",
                "summary": f"Indexed knowledge item {item['knowledge_id']}",
                "findings": {"item": item},
                "evidence_ids": [],
            }
        elif action == "list":
            items = [v for v in self._store.values() if v.get("organisation_id") == org_id]
            result = {
                "status": "completed",
                "summary": f"{len(items)} knowledge item(s) for organisation",
                "findings": {"items": items},
                "evidence_ids": [],
            }
        elif action == "flag_stale":
            stale = self._flag_stale(org_id)
            result = {
                "status": "completed",
                "summary": f"{len(stale)} potentially stale item(s)",
                "findings": {"stale_items": stale},
                "evidence_ids": [],
            }
        else:
            # retrieve
            query = inputs.get("query", "")
            hits = self._retrieve(org_id, query)
            result = {
                "status": "completed",
                "summary": f"Retrieved {len(hits)} item(s) for query",
                "findings": {"items": hits},
                "evidence_ids": [],
            }

        result["recommendations"] = []
        result["assumptions"] = []
        result["confidence"] = ConfidenceInfo(
            level=ConfidenceLevel.HIGH, reason=ConfidenceReason.USER_PROVIDED
        ).model_dump()
        self.finish_run(output_summary=result["summary"])
        return result

    def _index(self, org_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        kid = new_id("KNOW-")
        item = {
            "knowledge_id": kid,
            "organisation_id": org_id,
            "title": inputs.get("title", "untitled"),
            "content": inputs.get("content", ""),
            "source": inputs.get("source", "user"),
            "category": inputs.get("category", "general"),
            "owner": inputs.get("owner", "system"),
            "confidence": inputs.get("confidence", 0.7),
            "version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "review_date": inputs.get("review_date"),
            "permissions": inputs.get("permissions", ["org_read"]),
            "tags": inputs.get("tags", []),
        }
        self._store[kid] = item
        return item

    def _retrieve(self, org_id: str, query: str) -> List[Dict[str, Any]]:
        q = query.lower()
        hits = []
        for item in self._store.values():
            if item.get("organisation_id") != org_id:
                continue
            blob = f"{item.get('title','')} {item.get('content','')} {' '.join(item.get('tags',[]))}".lower()
            if not q or q in blob:
                hits.append(item)
        return hits

    def _flag_stale(self, org_id: str) -> List[Dict[str, Any]]:
        stale = []
        now = datetime.now(timezone.utc)
        for item in self._store.values():
            if item.get("organisation_id") != org_id:
                continue
            review = item.get("review_date")
            if review:
                try:
                    rd = datetime.fromisoformat(review)
                    if rd < now:
                        stale.append(item)
                except ValueError:
                    pass
        return stale
