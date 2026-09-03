from enum import Enum

from pydantic import BaseModel, Field

from src.models.fact_checker.evidence import Evidence, RejectedEvidence
from src.models.fact_checker.pipeline_stage import PipelineStage


class Verdict(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    MISLEADING = "MISLEADING"
    UNVERIFIED = "UNVERIFIED"


class FactCheck(BaseModel):

    verdict: Verdict

    explanation: str

    confidence: float

    claim: str | None = None

    evidence: list[Evidence] = Field(default_factory=list)

    cited_evidence_indices: list[int] = Field(default_factory=list)

    evidence_count: int = 0

    rejected_sources: list[RejectedEvidence] = Field(default_factory=list)

    reached_stage: PipelineStage = PipelineStage.AGGREGATION

    stage_note: str | None = None

    raw_verdict: Verdict | None = None

    raw_confidence: float | None = None