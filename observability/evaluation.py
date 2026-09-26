"""Evaluation engine — deterministic first; LLM-judge is optional and never overrides FAIL."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from events.bus import bus
from persistence.unit_of_work import UnitOfWork
from schemas.common import new_id
from observability.models_db import (
    EvalDataset,
    EvalDatasetVersion,
    EvalResult,
    EvalRun,
    ObsDefect,
    ObsQualityProfile,
)
from observability.logging import redact_secrets


class EvaluationEngine:
    def create_dataset(
        self, organisation_id: str, name: str, description: str = ""
    ) -> Dict[str, Any]:
        did = new_id("EDS-")
        with UnitOfWork() as uow:
            uow.session.add(
                EvalDataset(
                    dataset_id=did,
                    organisation_id=organisation_id,
                    name=name,
                    description=description,
                )
            )
        return {"dataset_id": did, "name": name}

    def publish_version(
        self,
        organisation_id: str,
        dataset_id: str,
        version: str,
        cases: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        vid = new_id("EDV-")
        with UnitOfWork() as uow:
            ds = uow.session.get(EvalDataset, dataset_id)
            if not ds or ds.organisation_id != organisation_id:
                from core.errors import NotFoundError
                raise NotFoundError("Dataset not found")
            uow.session.add(
                EvalDatasetVersion(
                    version_id=vid,
                    dataset_id=dataset_id,
                    organisation_id=organisation_id,
                    version=version,
                    immutable=True,
                    cases=cases,
                )
            )
        return {"version_id": vid, "version": version, "case_count": len(cases)}

    def evaluate_case(self, case: Dict[str, Any], actual: Any) -> Dict[str, Any]:
        """Deterministic evaluation. Returns PASS|FAIL|UNKNOWN."""
        dimensions: Dict[str, Any] = {}
        status = "PASS"
        expected = case.get("expected_output")
        required_facts = case.get("required_facts") or []
        forbidden = case.get("forbidden_claims") or []
        required_tools = case.get("required_tools") or []
        forbidden_tools = case.get("forbidden_tools") or []
        expected_schema_keys = case.get("expected_schema_keys") or []

        actual_text = actual if isinstance(actual, str) else str(actual)
        actual_tools = case.get("_actual_tools") or (actual.get("tools") if isinstance(actual, dict) else []) or []

        # schema
        if expected_schema_keys and isinstance(actual, dict):
            missing = [k for k in expected_schema_keys if k not in actual]
            dimensions["schema_compliance"] = 1.0 if not missing else 0.0
            if missing:
                status = "FAIL"
        else:
            dimensions["schema_compliance"] = None

        # correctness by exact or contains
        if expected is not None:
            if isinstance(expected, str):
                ok = expected.strip().lower() in actual_text.lower() or actual_text.strip() == expected.strip()
            else:
                ok = actual == expected
            dimensions["correctness"] = 1.0 if ok else 0.0
            if not ok:
                status = "FAIL"
        else:
            dimensions["correctness"] = None

        # required facts
        if required_facts:
            found = sum(1 for f in required_facts if str(f).lower() in actual_text.lower())
            dimensions["completeness"] = found / len(required_facts)
            if found < len(required_facts):
                status = "FAIL"
        else:
            dimensions["completeness"] = None

        # forbidden claims
        if forbidden:
            hit = [f for f in forbidden if str(f).lower() in actual_text.lower()]
            dimensions["safety"] = 0.0 if hit else 1.0
            if hit:
                status = "FAIL"
        else:
            dimensions["safety"] = None

        # tools
        if required_tools:
            ok_t = all(t in actual_tools for t in required_tools)
            dimensions["tool_use_correctness"] = 1.0 if ok_t else 0.0
            if not ok_t:
                status = "FAIL"
        if forbidden_tools:
            bad = [t for t in forbidden_tools if t in actual_tools]
            if bad:
                dimensions["tool_use_correctness"] = 0.0
                status = "FAIL"

        # grounding: if required_sources listed and actual provides citations
        required_sources = case.get("required_sources") or []
        if required_sources:
            cites = case.get("_actual_sources") or (actual.get("sources") if isinstance(actual, dict) else []) or []
            ok_g = all(s in cites for s in required_sources)
            dimensions["grounding"] = 1.0 if ok_g else 0.0
            if not ok_g:
                status = "FAIL"
        else:
            dimensions["grounding"] = None

        # if nothing evaluable
        if all(v is None for v in dimensions.values()) and expected is None:
            status = "UNKNOWN"

        return {
            "status": status,
            "dimensions": dimensions,
            "method": "deterministic",
            "case_id": case.get("case_id"),
        }

    def run_dataset(
        self,
        organisation_id: str,
        version_id: str,
        executor,
        *,
        system_version: str = "1.0.0",
    ) -> Dict[str, Any]:
        """executor(case) -> actual output"""
        with UnitOfWork() as uow:
            ver = uow.session.get(EvalDatasetVersion, version_id)
            if not ver or ver.organisation_id != organisation_id:
                from core.errors import NotFoundError
                raise NotFoundError("Dataset version not found")
            cases = list(ver.cases or [])

        run_id = new_id("ERUN-")
        with UnitOfWork() as uow:
            uow.session.add(
                EvalRun(
                    run_id=run_id,
                    organisation_id=organisation_id,
                    dataset_version_id=version_id,
                    system_version=system_version,
                    status="RUNNING",
                    cases_total=len(cases),
                )
            )
        bus.publish("evaluation.started", {"run_id": run_id}, organisation_id=organisation_id)

        passed = failed = unknown = 0
        results = []
        for case in cases:
            try:
                actual = executor(case)
            except Exception as e:
                actual = {"error": str(e)}
            ev = self.evaluate_case(case, actual)
            if ev["status"] == "PASS":
                passed += 1
            elif ev["status"] == "FAIL":
                failed += 1
            else:
                unknown += 1
            rid = new_id("ERES-")
            with UnitOfWork() as uow:
                uow.session.add(
                    EvalResult(
                        result_id=rid,
                        run_id=run_id,
                        organisation_id=organisation_id,
                        case_id=case.get("case_id"),
                        status=ev["status"],
                        dimensions=ev["dimensions"],
                        expected=redact_secrets({"expected": case.get("expected_output")}),
                        actual=redact_secrets({"actual": actual if not isinstance(actual, str) else actual[:2000]}),
                        evidence={"method": "deterministic"},
                        method="deterministic",
                    )
                )
            results.append(ev)

        status = "COMPLETED"
        with UnitOfWork() as uow:
            run = uow.session.get(EvalRun, run_id)
            if run:
                run.status = status
                run.cases_passed = passed
                run.cases_failed = failed
                run.cases_unknown = unknown
                run.metrics = {
                    "pass_rate": passed / len(cases) if cases else 0.0,
                    "fail_rate": failed / len(cases) if cases else 0.0,
                }
                run.completed_at = datetime.utcnow()

        bus.publish(
            "evaluation.completed",
            {"run_id": run_id, "passed": passed, "failed": failed},
            organisation_id=organisation_id,
        )
        if failed:
            bus.publish("regression.detected", {"run_id": run_id, "failed": failed}, organisation_id=organisation_id)

        return {
            "run_id": run_id,
            "status": status,
            "cases_total": len(cases),
            "cases_passed": passed,
            "cases_failed": failed,
            "cases_unknown": unknown,
            "results": results,
        }

    def detect_regression(
        self, organisation_id: str, baseline_run_id: str, candidate_run_id: str, threshold: float = 0.0
    ) -> Dict[str, Any]:
        with UnitOfWork() as uow:
            base = uow.session.get(EvalRun, baseline_run_id)
            cand = uow.session.get(EvalRun, candidate_run_id)
            if not base or not cand:
                from core.errors import NotFoundError
                raise NotFoundError("Run not found")
            if base.organisation_id != organisation_id or cand.organisation_id != organisation_id:
                from core.errors import AuthorizationError
                raise AuthorizationError("Cross-tenant evaluation access denied")
            base_rate = (base.metrics or {}).get("pass_rate", 0)
            cand_rate = (cand.metrics or {}).get("pass_rate", 0)
            drop = base_rate - cand_rate
            regressed = drop > threshold
            return {
                "regressed": regressed,
                "baseline_pass_rate": base_rate,
                "candidate_pass_rate": cand_rate,
                "drop": drop,
                "threshold": threshold,
            }

    def update_quality_profile(
        self,
        organisation_id: str,
        subject_type: str,
        subject_key: str,
        metrics: Dict[str, Any],
        version: str = "1.0.0",
    ) -> Dict[str, Any]:
        pid = new_id("QP-")
        with UnitOfWork() as uow:
            existing = (
                uow.session.query(ObsQualityProfile)
                .filter_by(
                    organisation_id=organisation_id,
                    subject_type=subject_type,
                    subject_key=subject_key,
                    version=version,
                )
                .one_or_none()
            )
            if existing:
                existing.metrics = metrics
                existing.updated_at = datetime.utcnow()
                pid = existing.profile_id
            else:
                uow.session.add(
                    ObsQualityProfile(
                        profile_id=pid,
                        organisation_id=organisation_id,
                        subject_type=subject_type,
                        subject_key=subject_key,
                        version=version,
                        metrics=metrics,
                    )
                )
        return {"profile_id": pid, "subject_type": subject_type, "subject_key": subject_key, "metrics": metrics}

    def create_defect(
        self,
        organisation_id: str,
        description: str,
        *,
        expected: str = "",
        actual: str = "",
        category: str = "quality",
        evidence: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        did = new_id("DEF-")
        with UnitOfWork() as uow:
            uow.session.add(
                ObsDefect(
                    defect_id=did,
                    organisation_id=organisation_id,
                    category=category,
                    description=description,
                    expected=expected,
                    actual=actual,
                    evidence=evidence or {},
                )
            )
        return {"defect_id": did, "status": "OPEN"}
