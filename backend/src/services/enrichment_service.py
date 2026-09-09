from logging import getLogger
from typing import Callable, Optional
from uuid import uuid4

from src.config.thresholds import PipelineThresholds
from src.models.core.enriched_article import EnrichedArticle
from src.models.core.news import News
from src.workflows.enrichment import NewsEnrichmentPipeline

logger = getLogger(__name__)

OnPhase = Callable[[str, dict], None]


def _noop(phase: str, data: dict) -> None:
    pass


class EnrichmentService:
    """
    Runs the NLP enrichment stage on text supplied directly, without
    scraping or fact-checking around it.

    This is the article pipeline's middle stage on its own. It reuses
    NewsEnrichmentPipeline unchanged - the same keyword, entity, claim,
    topic, sentiment, quality and embedding processors, driven by the
    same per-run thresholds - so what you see here is exactly what the
    full pipeline would derive from the same text.

    Deliberately side-effect free: nothing is written to the lake. This
    is an inspection and tuning tool ("what would the pipeline make of
    this text, at these thresholds?"), and writing a record for every
    experiment would fill the raw layer with text that was never
    fetched from anywhere.
    """

    def __init__(self, pipeline: NewsEnrichmentPipeline):
        self.pipeline = pipeline

    def enrich(
        self,
        text: str,
        title: str | None = None,
        url: str | None = None,
        language: str | None = None,
        on_phase: Optional[OnPhase] = None,
        thresholds: PipelineThresholds | None = None,
    ) -> dict:

        report_phase = on_phase or _noop

        thresholds = thresholds or PipelineThresholds()

        report_phase("enriching", {"thresholds": thresholds.model_dump()})

        article = self.pipeline.process(
            self._as_news(text, title, url, language),
            thresholds,
        )

        result = self._shape(article, thresholds)

        report_phase("enriched", result)

        return result

    @staticmethod
    def _as_news(
        text: str,
        title: str | None,
        url: str | None,
        language: str | None = None,
    ) -> News:
        """
        NewsEnrichmentPipeline takes a News, so pasted text is wrapped in
        a synthetic one. source_id "manual" and a generated id mark it as
        never having been fetched from a configured source - it is not
        persisted, but if it ever were, it must not masquerade as a
        scraped article.
        """

        return News(
            id=uuid4().hex,
            source_id="manual",
            url=url or "about:blank",
            title=title,
            # None means "detect it" - NewsEnrichmentPipeline falls back
            # to LanguageDetector. An explicit value is for the caller who
            # knows better than a stopword count (a short fragment, say).
            language=language,
            content=text,
        )

    @staticmethod
    def _shape(article: EnrichedArticle, thresholds: PipelineThresholds) -> dict:

        sentiment = article.sentiment
        quality = article.quality

        return {
            "title": article.title,
            "language": article.language,
            "keywords": article.keywords or [],
            "entities": article.entities or {},
            "topics": [topic.model_dump() for topic in (article.topics or [])],
            "claims": [
                {
                    "text": claim.text,
                    "confidence": claim.confidence,
                    "entities": claim.entities,
                }
                for claim in (article.claims or [])
            ],
            "sentiment": {
                "label": sentiment.label,
                "positive": sentiment.positive,
                "neutral": sentiment.neutral,
                "negative": sentiment.negative,
                "polarity": sentiment.polarity,
                "subjectivity": sentiment.subjectivity,
                "confidence": sentiment.confidence,
                "emotionalIntensity": sentiment.emotional_intensity,
            },
            "quality": {
                "readability": quality.readability,
                "objectivity": quality.objectivity,
                "constructiveness": quality.constructiveness,
                "inspirationalScore": quality.inspirational_score,
                "hopefulness": quality.hopefulness,
                "societalImpact": quality.societal_impact,
                "novelty": quality.novelty,
            },
            # The vector itself is 1024 floats - useless to a UI and
            # bigger than everything else here combined. Report its shape
            # and which model produced it instead.
            "embedding": {
                "model": article.embedding_model,
                "dimension": article.embedding_dimension,
                "preview": article.embedding[:8],
            },
            "thresholds": thresholds.model_dump(),
        }
