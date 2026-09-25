"""Base agent interface — all specialists inherit from this."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from schemas.agents import AgentMessage, AgentProfile, AgentRunRecord
from schemas.common import ConfidenceInfo, TaskState
from schemas.evidence import Evidence
from agents.registry import get_agent


class BaseAgent(ABC):
    """Abstract base for every CINTEXA BI specialist."""

    agent_id: str = "base"

    def __init__(self):
        profile = get_agent(self.agent_id)
        if profile is None:
            raise ValueError(f"Agent '{self.agent_id}' not found in registry")
        self.profile: AgentProfile = profile
        self._run: Optional[AgentRunRecord] = None

    @property
    def name(self) -> str:
        return self.profile.name

    def can_use_tool(self, tool_name: str) -> bool:
        for p in self.profile.permissions:
            if p.tool_name == tool_name:
                return p.allowed
        return False

    def requires_approval(self, tool_name: str) -> bool:
        for p in self.profile.permissions:
            if p.tool_name == tool_name:
                return p.requires_approval
        return False

    def start_run(self, task_id: str, input_summary: str = "") -> AgentRunRecord:
        self._run = AgentRunRecord(
            agent_id=self.agent_id,
            task_id=task_id,
            status=TaskState.RUNNING,
            input_summary=input_summary,
            started_at=datetime.now(timezone.utc),
        )
        return self._run

    def finish_run(
        self,
        status: TaskState = TaskState.COMPLETED,
        output_summary: str = "",
        evidence_ids: Optional[List[str]] = None,
        errors: Optional[List[str]] = None,
        tools_used: Optional[List[str]] = None,
        qa_result: Optional[str] = None,
    ) -> AgentRunRecord:
        if self._run is None:
            raise RuntimeError("No active run")
        self._run.status = status
        self._run.output_summary = output_summary
        self._run.evidence_ids = evidence_ids or []
        self._run.errors = errors or []
        self._run.tools_used = tools_used or self._run.tools_used
        if qa_result is not None:
            self._run.qa_result = qa_result
        self._run.completed_at = datetime.now(timezone.utc)
        if self._run.started_at:
            delta = self._run.completed_at - self._run.started_at
            self._run.duration_ms = int(delta.total_seconds() * 1000)
        return self._run

    def build_message(
        self,
        task_id: str,
        to_agent: str,
        message_type: str,
        data: Dict[str, Any],
        evidence_ids: Optional[List[str]] = None,
        confidence: Optional[ConfidenceInfo] = None,
        requires_response: bool = False,
    ) -> AgentMessage:
        from schemas.common import MessageType, Priority

        return AgentMessage(
            task_id=task_id,
            from_agent=self.agent_id,
            to_agent=to_agent,
            message_type=MessageType(message_type),
            priority=Priority.MEDIUM,
            data=data,
            evidence_ids=evidence_ids or [],
            confidence=confidence,
            requires_response=requires_response,
        )

    @abstractmethod
    async def execute(
        self,
        task_id: str,
        context: Dict[str, Any],
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute the agent's responsibility.
        Must never fabricate market stats, competitor data, financial figures,
        citations or forecasts. Mark unavailable information explicitly.
        """
        ...

    def unavailable(self, item: str, reason: str = "not supplied or not retrieved") -> Dict[str, Any]:
        return {
            "status": "unavailable",
            "item": item,
            "reason": reason,
            "confidence": ConfidenceInfo(level="UNKNOWN", reason="MODEL_GENERATED").model_dump(),
        }
