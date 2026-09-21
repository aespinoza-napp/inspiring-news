from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from src.models.fact_checker.pipeline_stage import PipelineStage


class EvidenceOrigin(str, Enum):
    WEB = "web"
    INTERNAL = "internal"


class EvidenceStance(str, Enum):
    """
    What this particular source says about the claim, as judged during
    LLM verification. Distinct from the claim's own verdict: a claim can
    be PARTIALLY_TRUE precisely because its sources disagree, and that
    disagreement is only visible per source.
    """

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    UNRELATED = "unrelated"


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

    # Registrable domain, used to judge whether two pieces of evidence are
    # actually independent. Five outlets running the same wire story are
    # five URLs but nothing like five confirmations.
    domain: Optional[str] = None

    # Which SearXNG engines surfaced this result. Free in the JSON
    # response, and the cheapest available signal that two hits came from
    # genuinely different indexes rather than one.
    engines: list[str] = Field(default_factory=list)

    # Which of the claim's queries returned this page (QueryKind values:
    # anchor / proposition / refutation). A hit only the anchor query
    # found is about the claim's *subject*; one the proposition query
    # found too is about what the claim actually asserts. That difference
    # is what an etymology page and a real source look like from here.
    found_by: list[str] = Field(default_factory=list)

    # Reciprocal-rank fusion score across those queries - how much they
    # agreed this page was worth returning. Decides which candidates are
    # expensive enough to scrape, before any of them has been read.
    fusion_score: Optional[float] = None

    # ---- ranking breakdown --------------------------------------------
    #
    # EvidenceRanker combines these three into relevance_score. They are
    # retained rather than discarded so the interface can answer "why was
    # this ranked above that one" with the actual arithmetic instead of a
    # single opaque number.

    semantic_score: Optional[float] = None

    # How many of the claim's own discriminative terms this source
    # contains. The counterweight to semantic_score, which cannot tell a
    # page that addresses the assertion from one that merely shares its
    # subject - see services/fact_checker/terms.py.
    lexical_score: Optional[float] = None

    recency_score: Optional[float] = None

    reliability_score: Optional[float] = None

    # Whether reliability_score is a rating we actually hold for this
    # domain, or just RANKING_DEFAULT_RELIABILITY because we know nothing
    # about it. A default 0.5 shown next to a real 0.9 reads as a verdict
    # on the source that nobody ever made.
    reliability_known: bool = False

    # Semantic and lexical agreement combined: whether this source
    # addresses the claim at all, as opposed to how highly it ranks among
    # those that do. Below the run's evidence_min_pertinence a source is
    # cut before verification, so it can never be cited, counted, or
    # treated as corroboration.
    pertinence_score: Optional[float] = None

    # ---- verification ---------------------------------------------------

    stance: Optional[EvidenceStance] = None

    # The span of this source the LLM says it relied on. Only ever set
    # when the span was found verbatim in the source text - see
    # LLMVerifier, which drops quotes it cannot locate rather than
    # forwarding a model's paraphrase as if it were a quotation.
    quote: Optional[str] = None
