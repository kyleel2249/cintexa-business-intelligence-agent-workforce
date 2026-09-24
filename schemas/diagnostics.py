"""Business Diagnostic Framework — configurable pillars and Health Score."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from schemas.common import ConfidenceInfo, new_id


DEFAULT_PILLARS = [
    "Strategy",
    "Sales",
    "Marketing",
    "Customers",
    "Operations",
    "Finance",
    "Technology",
    "Automation",
    "Data",
    "Risk",
]


class PillarMetric(BaseModel):
    name: str
    value: Optional[float] = None
    unit: Optional[str] = None
    period: Optional[str] = None
    source: Optional[str] = None
    calculation_method: Optional[str] = None
    confidence: ConfidenceInfo = Field(default_factory=ConfidenceInfo)
    data_type: str = "measured"  # measured | estimated | inferred | user_provided


class PillarScore(BaseModel):
    pillar: str
    score: Optional[float] = Field(None, ge=0, le=100)
    confidence: ConfidenceInfo = Field(default_factory=ConfidenceInfo)
    metrics: List[PillarMetric] = Field(default_factory=list)
    observations: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    methodology: Optional[str] = None


class BusinessHealthReport(BaseModel):
    diagnostic_id: str = Field(default_factory=lambda: new_id("DIAG-"))
    organisation_id: str
    business_profile_id: Optional[str] = None
    overall_score: Optional[float] = Field(None, ge=0, le=100)
    overall_confidence: ConfidenceInfo = Field(default_factory=ConfidenceInfo)
    pillars: List[PillarScore] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    opportunities: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    priority_areas: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    methodology: str = (
        "Scores are derived from available metrics, user-provided data and "
        "documented evidence. Pillars without data are scored as UNKNOWN and "
        "excluded from the overall average unless an explicit estimate is supplied."
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    task_id: Optional[str] = None

    def compute_overall(self) -> None:
        scored = [p.score for p in self.pillars if p.score is not None]
        if scored:
            self.overall_score = round(sum(scored) / len(scored), 1)
        else:
            self.overall_score = None
