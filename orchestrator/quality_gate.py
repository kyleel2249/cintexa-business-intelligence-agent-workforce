"""Quality gates at planning, execution, evidence, reasoning, synthesis, final."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from schemas.missions import Mission, MissionTaskStatus


@dataclass
class GateResult:
    gate: str
    passed: bool
    warnings: List[str] = field(default_factory=list)
    confidence: float = 0.0
    issues: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)


class QualityGate:
    def planning(self, mission: Mission) -> GateResult:
        issues = []
        if not mission.tasks:
            issues.append("No tasks in plan")
        if not mission.assigned_agents:
            issues.append("No agents assigned")
        return GateResult(
            gate="planning",
            passed=len(issues) == 0,
            issues=issues,
            confidence=0.8 if not issues else 0.3,
            recommended_actions=["Replan with clearer objective"] if issues else [],
        )

    def execution(self, mission: Mission) -> GateResult:
        total = max(1, len(mission.tasks))
        completed = sum(1 for t in mission.tasks if t.status == MissionTaskStatus.COMPLETED)
        failed = sum(1 for t in mission.tasks if t.status == MissionTaskStatus.FAILED)
        ratio = completed / total
        issues = []
        if failed and completed == 0:
            issues.append("All tasks failed")
        warnings = []
        if failed:
            warnings.append(f"{failed} task(s) failed")
        return GateResult(
            gate="execution",
            passed=ratio >= 0.4 or completed >= 1,
            warnings=warnings,
            issues=issues,
            confidence=ratio,
        )

    def evidence(self, mission: Mission) -> GateResult:
        n = len(mission.evidence or [])
        conf = mission.confidence or 0.0
        issues = []
        if n == 0 and conf < 0.5:
            issues.append("Weak evidence base")
        return GateResult(
            gate="evidence",
            passed=n > 0 or conf >= 0.5,
            confidence=conf,
            issues=issues,
            warnings=["Limited evidence — treat conclusions as provisional"] if n < 2 else [],
        )

    def final(self, mission: Mission) -> GateResult:
        r = mission.result
        issues = []
        if not r or not r.summary:
            issues.append("Missing final summary")
        return GateResult(
            gate="final_output",
            passed=len(issues) == 0,
            issues=issues,
            confidence=mission.confidence or 0.0,
            recommended_actions=["Run synthesis again"] if issues else [],
        )

    def run_all(self, mission: Mission) -> List[GateResult]:
        return [
            self.planning(mission),
            self.execution(mission),
            self.evidence(mission),
            self.final(mission),
        ]


quality_gate = QualityGate()
