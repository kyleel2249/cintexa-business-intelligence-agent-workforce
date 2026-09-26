"""Agent Runtime — assign, execute, handoff, escalate, graph run."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from core.errors import ConflictError, ExecutionError, NotFoundError, ValidationError
from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from agent_os.contracts import validate_input, validate_output, DEFAULT_INPUT_SCHEMAS, DEFAULT_OUTPUT_SCHEMAS
from agent_os.lifecycle import AgentLifecycleState, can_accept_new_work, can_continue_work
from agent_os.models_db import (
    AgentExecutionRecord,
    AgentMessageRecordOS,
    EscalationRecord,
    RegisteredAgent,
    WorkflowGraphNode,
)
from agent_os.registry import AgentOSRegistry
from events.bus import bus


class AgentRuntime:
    def __init__(self, registry: Optional[AgentOSRegistry] = None):
        self.registry = registry or AgentOSRegistry()
        # Optional in-process handlers: agent_key → async/sync callable
        self._handlers: Dict[str, Callable] = {}

    def register_handler(self, agent_key: str, handler: Callable) -> None:
        self._handlers[agent_key] = handler

    def assign(
        self,
        *,
        organisation_id: str,
        capability: str,
        task_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
    ) -> RegisteredAgent:
        agent = self.registry.select_agent(organisation_id, capability)
        if not agent:
            raise NotFoundError(f"No eligible agent for capability '{capability}'")
        with UnitOfWork() as uow:
            row = uow.session.get(RegisteredAgent, agent.id)
            if not row or row.organisation_id != organisation_id:
                raise NotFoundError("Agent not found")
            state = AgentLifecycleState(row.lifecycle_state)
            if not can_accept_new_work(state):
                raise ConflictError(f"Agent {row.agent_key} cannot accept new work ({state.value})")
            row.in_flight = (row.in_flight or 0) + 1
            uow.session.expunge(row)
            return row

    def execute(
        self,
        *,
        organisation_id: str,
        agent_id: str,
        input_data: Dict[str, Any],
        task_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        input_schema: Optional[Dict] = None,
        output_schema: Optional[Dict] = None,
        capability: Optional[str] = None,
    ) -> Dict[str, Any]:
        with UnitOfWork() as uow:
            agent = uow.session.get(RegisteredAgent, agent_id)
            if not agent or agent.organisation_id != organisation_id:
                raise NotFoundError("Agent not found")
            state = AgentLifecycleState(agent.lifecycle_state)
            if not can_continue_work(state):
                raise ConflictError(f"Agent cannot execute in state {state.value}")
            agent_key = agent.agent_key
            version = agent.version
            # idempotency: same task+agent already completed?
            if task_id:
                prior = (
                    uow.session.query(AgentExecutionRecord)
                    .filter_by(
                        organisation_id=organisation_id,
                        agent_id=agent_id,
                        task_id=task_id,
                        status="COMPLETED",
                    )
                    .first()
                )
                if prior:
                    return {
                        "execution_id": prior.execution_id,
                        "status": "COMPLETED",
                        "output": prior.output_ref,
                        "idempotent": True,
                        "agent_key": agent_key,
                        "agent_version": version,
                    }

        # Contracts
        cap = capability or agent_key
        schema_in = input_schema or DEFAULT_INPUT_SCHEMAS.get(cap)
        schema_out = output_schema or DEFAULT_OUTPUT_SCHEMAS.get(cap)
        validate_input(schema_in, input_data)

        execution_id = new_id("EXEC-")
        with UnitOfWork() as uow:
            rec = AgentExecutionRecord(
                execution_id=execution_id,
                organisation_id=organisation_id,
                agent_id=agent_id,
                agent_key=agent_key,
                agent_version=version,
                task_id=task_id,
                workflow_id=workflow_id,
                status="RUNNING",
                input_ref=input_data,
                correlation_id=correlation_id or new_id("CORR-"),
                started_at=datetime.utcnow(),
            )
            uow.session.add(rec)

        bus.publish(
            "agent.execution.started",
            {"execution_id": execution_id, "agent_key": agent_key, "task_id": task_id},
            organisation_id=organisation_id,
            correlation_id=correlation_id,
            task_id=task_id,
            workflow_id=workflow_id,
        )

        error: Optional[str] = None
        output: Dict[str, Any] = {}
        status = "COMPLETED"
        try:
            handler = self._handlers.get(agent_key)
            if handler:
                result = handler(input_data)
                if hasattr(result, "__await__"):
                    raise ExecutionError("Async handlers require async execute path")
                output = result if isinstance(result, dict) else {"result": result}
            else:
                # Default stub for registered agents without handlers
                output = {"status": "ok", "echo": input_data, "agent_key": agent_key}
                if schema_out and "findings" in (schema_out.get("required") or []):
                    output = {"findings": [{"summary": f"Processed by {agent_key}", "input": input_data}]}
                if schema_out and "analysis" in (schema_out.get("required") or []):
                    output = {"analysis": {"summary": f"Analysed by {agent_key}", "input": input_data}}
            validate_output(schema_out, output)
        except ValidationError:
            raise
        except Exception as e:
            status = "FAILED"
            error = str(e)
            output = {}

        with UnitOfWork() as uow:
            rec = uow.session.get(AgentExecutionRecord, execution_id)
            if rec:
                rec.status = status
                rec.output_ref = output
                rec.error = error
                rec.completed_at = datetime.utcnow()
            agent = uow.session.get(RegisteredAgent, agent_id)
            if agent and (agent.in_flight or 0) > 0:
                agent.in_flight = agent.in_flight - 1

        self.registry.record_health(agent_id, organisation_id, success=(status == "COMPLETED"), error=error)

        bus.publish(
            "agent.execution.completed" if status == "COMPLETED" else "agent.execution.failed",
            {"execution_id": execution_id, "agent_key": agent_key, "status": status, "error": error},
            organisation_id=organisation_id,
            task_id=task_id,
            workflow_id=workflow_id,
        )

        if status == "FAILED":
            raise ExecutionError(error or "Agent execution failed")
        return {
            "execution_id": execution_id,
            "status": status,
            "output": output,
            "agent_key": agent_key,
            "agent_version": version,
        }

    def handoff(
        self,
        *,
        organisation_id: str,
        sender: str,
        recipient: str,
        payload: Dict[str, Any],
        task_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        mid = new_id("MSG-")
        with UnitOfWork() as uow:
            msg = AgentMessageRecordOS(
                message_id=mid,
                organisation_id=organisation_id,
                message_type="HANDOFF",
                sender=sender,
                recipient=recipient,
                task_id=task_id,
                workflow_id=workflow_id,
                correlation_id=correlation_id or new_id("CORR-"),
                payload=payload,
            )
            uow.session.add(msg)
        bus.publish(
            "agent.handoff",
            {"message_id": mid, "sender": sender, "recipient": recipient},
            organisation_id=organisation_id,
            correlation_id=correlation_id,
        )
        return {"message_id": mid, "message_type": "HANDOFF", "sender": sender, "recipient": recipient, "payload": payload}

    def request_clarification(
        self,
        *,
        organisation_id: str,
        agent_key: str,
        missing_fields: List[str],
        task_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        mid = new_id("MSG-")
        with UnitOfWork() as uow:
            uow.session.add(
                AgentMessageRecordOS(
                    message_id=mid,
                    organisation_id=organisation_id,
                    message_type="CLARIFICATION",
                    sender=agent_key,
                    recipient="user",
                    task_id=task_id,
                    workflow_id=workflow_id,
                    correlation_id=new_id("CORR-"),
                    payload={"missing_fields": missing_fields},
                )
            )
            if workflow_id:
                from database.models import WorkflowRecord

                wf = uow.session.get(WorkflowRecord, workflow_id)
                if wf and wf.organisation_id == organisation_id:
                    wf.status = "WAITING"
                    wf.current_state = "AWAITING_CLARIFICATION"
        return {"message_id": mid, "message_type": "CLARIFICATION", "missing_fields": missing_fields, "workflow_status": "WAITING"}

    def escalate(
        self,
        *,
        organisation_id: str,
        reason: str,
        agent_key: Optional[str] = None,
        task_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        payload: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        eid = new_id("ESC-")
        with UnitOfWork() as uow:
            uow.session.add(
                EscalationRecord(
                    escalation_id=eid,
                    organisation_id=organisation_id,
                    task_id=task_id,
                    workflow_id=workflow_id,
                    agent_key=agent_key,
                    reason=reason,
                    status="OPEN",
                    payload=payload or {},
                )
            )
            uow.session.add(
                AgentMessageRecordOS(
                    message_id=new_id("MSG-"),
                    organisation_id=organisation_id,
                    message_type="ESCALATION",
                    sender=agent_key or "system",
                    recipient="human",
                    task_id=task_id,
                    workflow_id=workflow_id,
                    correlation_id=new_id("CORR-"),
                    payload={"escalation_id": eid, "reason": reason},
                )
            )
            if workflow_id:
                from database.models import WorkflowRecord

                wf = uow.session.get(WorkflowRecord, workflow_id)
                if wf and wf.organisation_id == organisation_id:
                    wf.status = "WAITING"
                    wf.current_state = "AWAITING_HUMAN"
        bus.publish(
            "agent.escalation",
            {"escalation_id": eid, "reason": reason},
            organisation_id=organisation_id,
        )
        return {"escalation_id": eid, "status": "OPEN", "workflow_status": "WAITING"}

    def get_escalation(self, escalation_id: str, organisation_id: str) -> Optional[EscalationRecord]:
        with UnitOfWork() as uow:
            row = uow.session.get(EscalationRecord, escalation_id)
            if not row or row.organisation_id != organisation_id:
                return None
            uow.session.expunge(row)
            return row

    # ── Workflow graph ──────────────────────────────────────────

    def create_graph(
        self,
        *,
        organisation_id: str,
        workflow_id: str,
        nodes: List[Dict[str, Any]],
    ) -> List[WorkflowGraphNode]:
        """
        nodes: [{name, agent_key?, capability?, depends_on: [names], input_data?}]
        """
        name_to_id: Dict[str, str] = {}
        created: List[WorkflowGraphNode] = []
        with UnitOfWork() as uow:
            for i, n in enumerate(nodes):
                nid = new_id("NODE-")
                name_to_id[n["name"]] = nid
            for i, n in enumerate(nodes):
                deps = [name_to_id[d] for d in (n.get("depends_on") or []) if d in name_to_id]
                node = WorkflowGraphNode(
                    node_id=name_to_id[n["name"]],
                    workflow_id=workflow_id,
                    organisation_id=organisation_id,
                    name=n["name"],
                    agent_key=n.get("agent_key"),
                    capability=n.get("capability"),
                    depends_on=deps,
                    input_data=n.get("input_data") or {},
                    sequence=i,
                    status="PENDING",
                )
                uow.session.add(node)
            uow.session.flush()
            for nid in name_to_id.values():
                row = uow.session.get(WorkflowGraphNode, nid)
                if row:
                    uow.session.expunge(row)
                    created.append(row)
        return created

    def run_graph(self, *, organisation_id: str, workflow_id: str) -> Dict[str, Any]:
        """Execute ready nodes in waves until complete or blocked."""
        waves = 0
        outputs: Dict[str, Any] = {}
        while waves < 50:
            waves += 1
            with UnitOfWork() as uow:
                nodes = (
                    uow.session.query(WorkflowGraphNode)
                    .filter_by(workflow_id=workflow_id, organisation_id=organisation_id)
                    .all()
                )
                by_id = {n.node_id: n for n in nodes}
                ready = []
                for n in nodes:
                    if n.status not in ("PENDING", "READY"):
                        continue
                    deps_ok = all(
                        by_id[d].status == "COMPLETED" for d in (n.depends_on or []) if d in by_id
                    )
                    if deps_ok:
                        ready.append(n)
                if not ready:
                    break
                # snapshot ready node data before leaving session
                ready_data = [
                    {
                        "node_id": n.node_id,
                        "name": n.name,
                        "agent_key": n.agent_key,
                        "capability": n.capability,
                        "depends_on": list(n.depends_on or []),
                        "input_data": dict(n.input_data or {}),
                    }
                    for n in ready
                ]
                for n in ready:
                    n.status = "RUNNING"

            # Execute outside transaction (handlers may be slow)
            for rd in ready_data:
                # Merge dependency outputs into input
                dep_outputs = {}
                with UnitOfWork() as uow:
                    for d in rd["depends_on"]:
                        dep = uow.session.get(WorkflowGraphNode, d)
                        if dep and dep.output_data:
                            dep_outputs[dep.name] = dep.output_data
                input_data = {**rd["input_data"], "upstream": dep_outputs}
                try:
                    capability = rd["capability"] or rd["agent_key"] or "research"
                    agent = self.registry.select_agent(organisation_id, capability)
                    if not agent and rd["agent_key"]:
                        agent = self.registry.get_by_key(organisation_id, rd["agent_key"])
                    if not agent:
                        raise NotFoundError(f"No agent for node {rd['name']}")
                    result = self.execute(
                        organisation_id=organisation_id,
                        agent_id=agent.id,
                        input_data=input_data if input_data else {"query": rd["name"]},
                        task_id=rd["node_id"],
                        workflow_id=workflow_id,
                        capability=capability,
                        input_schema={"required": []},  # graph nodes may have flexible inputs
                        output_schema=None,
                    )
                    with UnitOfWork() as uow:
                        node = uow.session.get(WorkflowGraphNode, rd["node_id"])
                        if node:
                            node.status = "COMPLETED"
                            node.output_data = result.get("output") or {}
                            node.assigned_agent_id = agent.id
                            node.completed_at = datetime.utcnow()
                    outputs[rd["name"]] = result.get("output")
                except Exception as e:
                    with UnitOfWork() as uow:
                        node = uow.session.get(WorkflowGraphNode, rd["node_id"])
                        if node:
                            node.status = "FAILED"
                            node.output_data = {"error": str(e)}
                    outputs[rd["name"]] = {"error": str(e)}

        with UnitOfWork() as uow:
            nodes = (
                uow.session.query(WorkflowGraphNode)
                .filter_by(workflow_id=workflow_id, organisation_id=organisation_id)
                .all()
            )
            summary = {n.name: n.status for n in nodes}
        return {"workflow_id": workflow_id, "nodes": summary, "outputs": outputs, "waves": waves}
