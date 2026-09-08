from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.models.core.enriched_article import EnrichedArticle
from src.models.core.news import News
from src.models.fact_checker.fact_check import Verdict
from src.models.fact_checker.fact_check_report import FactCheckReport
from src.models.nlp.topic_prediction import TopicPrediction
from src.models.storage.lineage import DataLayer, Lineage


class RawRecord(BaseModel):
    """
    Layer 1. The article exactly as extracted, with the fetch metadata
    needed to explain or reproduce the fetch. Nothing here is derived
    from a model, so this layer stays valid even when every downstream
    model is replaced.
    """

    record_id: str

    layer: DataLayer = DataLayer.RAW

    lineage: Lineage

    article: News

    fetched_at: datetime = Field(default_factory=datetime.now)

    extractor: str = "unknown"

    content_length: int = 0


class ProcessedRecord(BaseModel):
    """
    Layer 2. The full analytical output - the enriched article and, when
    the article got that far, its fact-check report. Deliberately keeps
    everything, including what was rejected and why: this is the layer
    you debug and re-derive from, not the one you serve.
    """

    record_id: str

    layer: DataLayer = DataLayer.PROCESSED

    lineage: Lineage

    article: EnrichedArticle

    fact_check: Optional[FactCheckReport] = None


class ExploitationRecord(BaseModel):
    """
    Layer 3. One flat, denormalised document per article - the shape a
    serving database (or a search index) actually wants. No embeddings,
    no rejected candidates, no per-stage traces: just the decided facts
    plus the lineage needed to trace any field back to layer 2 and 1.

    `publishable` is the editorial decision, precomputed here so a reader
    never has to re-implement the rules: the article passed the admission
    filter and its aggregated verdict is not FALSE or MISLEADING.
    """

    record_id: str

    layer: DataLayer = DataLayer.EXPLOITATION

    lineage: Lineage

    # ---- identity -------------------------------------------------
    article_id: str

    url: str

    source_id: str

    title: str

    language: Optional[str] = None

    published_at: Optional[datetime] = None

    summary: str = ""

    # ---- classification -------------------------------------------
    primary_topic: Optional[str] = None

    topics: list[TopicPrediction] = Field(default_factory=list)

    keywords: list[str] = Field(default_factory=list)

    entities: dict[str, list[str]] = Field(default_factory=dict)

    # ---- scores ----------------------------------------------------
    sentiment_label: Optional[str] = None

    sentiment_positive: float = 0.0

    sentiment_negative: float = 0.0

    readability: float = 0.0

    objectivity: float = 0.0

    constructiveness: float = 0.0

    inspirational_score: float = 0.0

    societal_impact: float = 0.0

    impact_score: float = 0.0

    # ---- editorial decision ---------------------------------------
    publishable: bool = False

    validation_passed: bool = False

    rejection_reasons: list[str] = Field(default_factory=list)

    is_duplicate: bool = False

    verdict: Verdict = Verdict.UNVERIFIED

    verdict_confidence: float = 0.0

    claims_total: int = 0

    claims_checked: int = 0

    # Only the evidence that the LLM actually cited, flattened to URLs -
    # enough to show "sources" next to a published article without
    # dragging the whole processed record along.
    cited_evidence_urls: list[str] = Field(default_factory=list)

    # ---- pointers back to the heavy data ---------------------------
    # The vector lives in Qdrant (collection "news", point id =
    # article_id), not here - a 1024-float array in every serving
    # document would dwarf the document itself.
    vector_collection: Optional[str] = None

    embedding_model: Optional[str] = None

    embedding_dimension: Optional[int] = None
