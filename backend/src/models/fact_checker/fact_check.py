from enum import Enum

from pydantic import BaseModel, Field

from src.models.fact_checker.evidence import Evidence, RejectedEvidence
from src.models.fact_checker.pipeline_stage import PipelineStage


class Verdict(str, Enum):
    TRUE = "TRUE"
    # The central assertion holds but at least one source contradicts a
    # detail of it. Real verification lands here far more often than on
    # either absolute, and collapsing it into TRUE or MISLEADING loses
    # exactly the part a reader needs.
    PARTIALLY_TRUE = "PARTIALLY_TRUE"
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

    # What the sources confirm, and where they diverge - derived from the
    # per-source stances rather than from the LLM's prose, so the two
    # cannot disagree with each other.
    agreements: list[str] = Field(default_factory=list)

    discrepancies: list[str] = Field(default_factory=list)

    # How many distinct domains back this claim. The count that matters
    # for corroboration: evidence_count can be five copies of one wire
    # story, which is one source, not five.
    independent_domains: int = 0

    # True only when the LLM provider was never reached at all - distinct
    # from an ordinary UNVERIFIED, where the model was asked and found
    # nothing to confirm the claim with.
    llm_unreachable: bool = False