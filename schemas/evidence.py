"""Shared Evidence System — every claim references an evidence object."""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl

from schemas.common import Classification, ConfidenceLevel, SourceQuality, new_id


class EvidenceCreate(BaseModel):
    claim: str
    source: str
    source_type: str = "web"  # official, academic, news, company, government, dataset, user
    published_date: Optional[date] = None
    retrieved_date: date = Field(default_factory=date.today)
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    classification: Classification = Classification.UNKNOWN
    source_quality: SourceQuality = SourceQuality.C
    supports: List[str] = Field(default_factory=list)
    organisation_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class Evidence(EvidenceCreate):
    evidence_id: str = Field(default_factory=lambda: new_id("EV-"))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EvidenceBundle(BaseModel):
    """Collection of evidence items referenced by a finding or report."""
    items: List[Evidence] = Field(default_factory=list)
    summary: Optional[str] = None

    def add(self, evidence: Evidence) -> None:
        self.items.append(evidence)

    def by_id(self, evidence_id: str) -> Optional[Evidence]:
        for e in self.items:
            if e.evidence_id == evidence_id:
                return e
        return None

    def ids(self) -> List[str]:
        return [e.evidence_id for e in self.items]
