from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from src.models.fact_checker.pipeline_stage import PipelineStage


class EvidenceOrigin(str, Enum):
    WEB = "web"
    INTERNAL = "internal"


class RejectedEvidence(BaseModel):
    """
    A candidate that was found (via SearXNG or the internal vector
    search) but did not make it into a claim's final evidence set -
    kept for transparency into why a claim ended up with the evidence
    it did, and what was available but discarded.
    """

    url: str

    title: str

    origin: EvidenceOrigin

    stage: PipelineStage

    reason: str

    score: Optional[float] = None


class Evidence(BaseModel):

    url: str

    title: str

    snippet: str = ""

    content: Optional[str] = None

    source_name: Optional[str] = None

    source_reliability: Optional[float] = None

    published_at: Optional[datetime] = None

    retrieved_at: datetime = Field(default_factory=datetime.now)

    origin: EvidenceOrigin

    relevance_score: Optional[float] = None
