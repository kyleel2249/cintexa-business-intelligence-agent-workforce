"""Task/workflow recovery and compensation foundation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from events.bus import bus
from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from reliability.dead_letter import DeadLetterQueue
from reliability.models_db import RelCompensation
from reliability.retry import RetryEngine, RetryPolicy
from reliability.taxonomy import classify_failure


class RecoveryService:
    """Resume from checkpoints; compensate failed saga steps; escalate when needed."""

    def __init__(self):
        self.dlq = DeadLetterQueue()

    def recover_workflow_steps(
        self,
        *,
        organisation_id: str,
        workflow_id: str,
        steps: List[Dict[str, Any]],
        runner: Callable[[Dict[str, Any]], Any],
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        steps: [{id, status, depends_on: [ids], payload}]
        Only re-run FAILED/PENDING steps whose dependencies are COMPLETED.
        """
        by_id = {s["id"]: dict(s) for s in steps}
        executed = []
        bus.publish("recovery.started", {"workflow_id": workflow_id}, organisation_id=organisation_id)

        # topological-ish waves
        remaining = set(by_id.keys())
        while remaining:
            progressed = False
            for sid in list(remaining):
                step = by_id[sid]
                if step.get("status") == "COMPLETED":
                    remaining.discard(sid)
                    progressed = True
                    continue
                deps = step.get("depends_on") or []
                if any(by_id[d].get("status") != "COMPLETED" for d in deps if d in by_id):
                    continue
                # run step with retry
                engine = RetryEngine(RetryPolicy(max_attempts=max_retries, min_delay_sec=0.01, jitter=False))
                result = engine.run(
                    lambda s=step: runner(s),
                    organisation_id=organisation_id,
                    scope_key=f"wf:{workflow_id}:{sid}",
                    sleep=False,
                )
                if result.success:
                    step["status"] = "COMPLETED"
                    step["output"] = result.result
                    executed.append(sid)
                    remaining.discard(sid)
                    progressed = True
                else:
                    step["status"] = "FAILED"
                    step["error"] = result.decision.reason if result.decision else "failed"
                    decision = result.decision or classify_failure(Exception(step["error"]))
                    if decision.terminal or result.exhausted:
                        self.dlq.enqueue(
                            organisation_id=organisation_id,
                            reason=step["error"],
                            category=decision.category.value if decision else "UNKNOWN_FAILURE",
                            source_type="workflow_step",
                            source_id=sid,
                            correlation_id=workflow_id,
                            attempts=len(result.attempts),
                            history=[{"attempt": a.attempt, "error": a.error} for a in result.attempts],
                            payload=step.get("payload") or {},
                        )
                        remaining.discard(sid)
                        progressed = True
                        bus.publish(
                            "recovery.failed",
                            {"workflow_id": workflow_id, "step_id": sid},
                            organisation_id=organisation_id,
                        )
                        return {
                            "workflow_id": workflow_id,
                            "status": "PARTIALLY_FAILED",
                            "steps": list(by_id.values()),
                            "executed": executed,
                        }
            if not progressed:
                break

        all_ok = all(s.get("status") == "COMPLETED" for s in by_id.values())
        status = "COMPLETED" if all_ok else "PARTIALLY_FAILED"
        bus.publish(
            "recovery.completed" if all_ok else "recovery.failed",
            {"workflow_id": workflow_id, "status": status},
            organisation_id=organisation_id,
        )
        return {"workflow_id": workflow_id, "status": status, "steps": list(by_id.values()), "executed": executed}

    def start_compensation(
        self,
        *,
        organisation_id: str,
        workflow_id: str,
        step_id: str,
        forward_op: str,
        compensation_op: str,
        payload: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        cid = new_id("CMP-")
        with UnitOfWork() as uow:
            uow.session.add(
                RelCompensation(
                    compensation_id=cid,
                    organisation_id=organisation_id,
                    workflow_id=workflow_id,
                    step_id=step_id,
                    status="STARTED",
                    forward_op=forward_op,
                    compensation_op=compensation_op,
                    payload=payload or {},
                )
            )
        bus.publish(
            "compensation.started",
            {"compensation_id": cid, "workflow_id": workflow_id, "step_id": step_id},
            organisation_id=organisation_id,
        )
        return {"compensation_id": cid, "status": "STARTED"}

    def complete_compensation(
        self, compensation_id: str, organisation_id: str, *, success: bool = True, error: str = ""
    ) -> Dict[str, Any]:
        with UnitOfWork() as uow:
            row = uow.session.get(RelCompensation, compensation_id)
            if not row or row.organisation_id != organisation_id:
                from core.errors import NotFoundError
                raise NotFoundError("Compensation not found")
            row.status = "COMPLETED" if success else "FAILED"
            row.error = error or None
            row.completed_at = datetime.utcnow()
        bus.publish(
            "compensation.completed" if success else "compensation.failed",
            {"compensation_id": compensation_id},
            organisation_id=organisation_id,
        )
        if not success:
            bus.publish(
                "human.escalation.created",
                {"compensation_id": compensation_id, "reason": error},
                organisation_id=organisation_id,
            )
        return {"compensation_id": compensation_id, "status": "COMPLETED" if success else "FAILED"}
