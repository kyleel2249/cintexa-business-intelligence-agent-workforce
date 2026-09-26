"""Experiment engine — baseline vs candidate, shadow mode."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, Optional

from core.errors import AuthorizationError, ValidationError
from events.bus import bus
from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from evolution.governance import change_freeze
from evolution.models_db import EvoExperiment
from observability.evaluation import EvaluationEngine


class ExperimentEngine:
    def create(
        self,
        organisation_id: str,
        *,
        proposal_id: Optional[str] = None,
        hypothesis: str = "",
        baseline: Optional[Dict] = None,
        candidate: Optional[Dict] = None,
        success_criteria: Optional[Dict] = None,
        failure_criteria: Optional[Dict] = None,
        shadow: bool = True,
    ) -> Dict[str, Any]:
        if change_freeze.emergency_stop:
            raise AuthorizationError("Emergency stop — experiments blocked")
        if not baseline or not candidate:
            raise ValidationError("baseline and candidate required")
        eid = new_id("EXP-")
        with UnitOfWork() as uow:
            uow.session.add(
                EvoExperiment(
                    experiment_id=eid,
                    organisation_id=organisation_id,
                    proposal_id=proposal_id,
                    hypothesis=hypothesis,
                    baseline=baseline,
                    candidate=candidate,
                    success_criteria=success_criteria or {"min_pass_rate_delta": 0.0},
                    failure_criteria=failure_criteria or {"max_fail_rate_increase": 0.1},
                    status="PLANNED",
                    shadow=shadow,
                )
            )
        return {"experiment_id": eid, "status": "PLANNED", "shadow": shadow}

    def run_offline(
        self,
        organisation_id: str,
        experiment_id: str,
        *,
        baseline_executor: Callable,
        candidate_executor: Callable,
        cases: list,
    ) -> Dict[str, Any]:
        """Offline eval of baseline vs candidate on same cases. Shadow by default."""
        with UnitOfWork() as uow:
            exp = uow.session.get(EvoExperiment, experiment_id)
            if not exp or exp.organisation_id != organisation_id:
                from core.errors import NotFoundError
                raise NotFoundError("Experiment not found")
            exp.status = "RUNNING"
            success_crit = dict(exp.success_criteria or {})
            failure_crit = dict(exp.failure_criteria or {})

        eng = EvaluationEngine()

        def _score(executor):
            passed = failed = 0
            for case in cases:
                try:
                    actual = executor(case)
                except Exception as e:
                    actual = {"error": str(e)}
                r = eng.evaluate_case(case, actual)
                if r["status"] == "PASS":
                    passed += 1
                elif r["status"] == "FAIL":
                    failed += 1
            total = max(1, len(cases))
            return {"pass_rate": passed / total, "fail_rate": failed / total, "passed": passed, "failed": failed}

        base = _score(baseline_executor)
        cand = _score(candidate_executor)
        delta = cand["pass_rate"] - base["pass_rate"]
        min_delta = float(success_crit.get("min_pass_rate_delta", 0.0))
        max_fail_inc = float(failure_crit.get("max_fail_rate_increase", 0.1))

        if cand["fail_rate"] - base["fail_rate"] > max_fail_inc:
            conclusion = "REGRESSED"
        elif delta >= min_delta and cand["pass_rate"] >= base["pass_rate"]:
            conclusion = "IMPROVED" if delta > 0 else "INCONCLUSIVE"
        elif cand["pass_rate"] < base["pass_rate"]:
            conclusion = "REGRESSED"
        else:
            conclusion = "INCONCLUSIVE"

        results = {
            "baseline": base,
            "candidate": cand,
            "delta_pass_rate": delta,
            "shadow": True,
            "production_affected": False,
        }
        with UnitOfWork() as uow:
            exp = uow.session.get(EvoExperiment, experiment_id)
            if exp and exp.organisation_id == organisation_id:
                exp.status = "COMPLETED"
                exp.results = results
                exp.conclusion = conclusion
                exp.completed_at = datetime.utcnow()

        bus.publish(
            "evolution.experiment.completed",
            {"experiment_id": experiment_id, "conclusion": conclusion},
            organisation_id=organisation_id,
        )
        return {
            "experiment_id": experiment_id,
            "status": "COMPLETED",
            "conclusion": conclusion,
            "results": results,
        }

    def get(self, experiment_id: str, organisation_id: str) -> Optional[Dict]:
        with UnitOfWork() as uow:
            exp = uow.session.get(EvoExperiment, experiment_id)
            if not exp or exp.organisation_id != organisation_id:
                return None
            return {
                "experiment_id": exp.experiment_id,
                "status": exp.status,
                "conclusion": exp.conclusion,
                "results": exp.results,
                "shadow": exp.shadow,
                "proposal_id": exp.proposal_id,
            }
