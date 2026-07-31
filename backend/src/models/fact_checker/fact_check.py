from enum import Enum

from pydantic import BaseModel, Field

from src.models.fact_checker.evidence import Evidence


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