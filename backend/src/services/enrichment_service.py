from logging import getLogger
from typing import Callable, Optional
from uuid import uuid4

from src.config.thresholds import PipelineThresholds
from src.models.core.enriched_article import EnrichedArticle
from src.models.core.news import News
from src.services.fact_checker.retrieval.scraper import EvidenceScraper
from src.services.scraper.extractor import ExtractorService
from src.services.scraper.request_stats import Purpose
from src.workflows.enrichment import NewsEnrichmentPipeline

logger = getLogger(__name__)

OnPhase = Callable[[str, dict], None]


class NothingToEnrich(ValueError):
    """No text was given and none could be fetched from the URL."""


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

    Given a URL, it first fetches the page with the same extractor the
    article analyzer uses, so the extraction itself can be inspected:
    what title, author, date and body the pipeline would have started
    from. Anything the caller supplies wins over what was extracted, and
    the response says which is which. That is how every article was
    found to have been analyzed without a title.

    Deliberately side-effect free: nothing is written to the lake. This
    is an inspection and tuning tool ("what would the pipeline make of
    this text, at these thresholds?"), and writing a record for every
    experiment would fill the raw layer with text nobody meant to ingest.
    """

    def __init__(
        self,
        pipeline: NewsEnrichmentPipeline,
        extractor: ExtractorService | None = None,
    ):
        self.pipeline = pipeline
        self.extractor = extractor or ExtractorService()

    def enrich(
        self,
        text: str | None = None,
        title: str | None = None,
        url: str | None = None,
        language: str | None = None,
        on_phase: Optional[OnPhase] = None,
        thresholds: PipelineThresholds | None = None,
    ) -> dict:

        report_phase = on_phase or _noop

        thresholds = thresholds or PipelineThresholds()

        text = (text or "").strip() or None
        title = (title or "").strip() or None
        url = (url or "").strip() or None

        fetched, fetch_error = self._fetch(url, thresholds) if url else (None, None)

        body = text or (fetched.content if fetched else None)

        if not body:
            raise NothingToEnrich(
                fetch_error or "Provide the article text, a URL to fetch it from, or both."
            )

        news = self._as_news(body, title, url, language, fetched)

        report_phase("enriching", {"thresholds": thresholds.model_dump()})

        article = self.pipeline.process(news, thresholds)

        result = {
            **self._shape(article, thresholds),
            "extraction": self._extraction(
                url, text, title, news, fetched, fetch_error,
            ),
        }

        report_phase("enriched", result)

        return result

    def _fetch(
        self,
        url: str,
        thresholds: PipelineThresholds,
    ) -> tuple[News | None, str | None]:
        """
        The page as the analyzer would see it, or why it could not be had.

        A failure is not raised when the caller also pasted the text: the
        text can still be enriched, and the page's metadata was a bonus.
        """

        try:
            news = self.extractor.extract(
                EvidenceScraper.GENERIC_SOURCE,
                url,
                thresholds,
                purpose=Purpose.ENRICHMENT,
            )
        except Exception as exc:
            logger.warning("Could not fetch %s for enrichment: %s", url, exc)
            return None, f"Failed to fetch the page: {exc}"

        if news is None:
            return None, (
                "Could not extract article content from this URL (blocked, "
                "unreachable, or too little text on the page)."
            )

        return news, None

    @staticmethod
    def _as_news(
        text: str,
        title: str | None,
        url: str | None,
        language: str | None = None,
        fetched: News | None = None,
    ) -> News:
        """
        NewsEnrichmentPipeline takes a News, so the input is wrapped in a
        synthetic one. source_id "manual" and a generated id mark it as
        not having come from a configured source - it is not persisted,
        but if it ever were, it must not masquerade as a scraped article.
        """

        return News(
            id=uuid4().hex,
            source_id="manual",
            url=url or "about:blank",
            title=title or (fetched.title if fetched else None),
            author=fetched.author if fetched else None,
            published_at=fetched.published_at if fetched else None,
            image_url=fetched.image_url if fetched else None,
            # None means "detect it" - NewsEnrichmentPipeline falls back
            # to LanguageDetector. An explicit value is for the caller who
            # knows better than a stopword count (a short fragment, say).
            language=language,
            content=text,
        )

    @staticmethod
    def _extraction(
        url: str | None,
        text: str | None,
        title: str | None,
        news: News,
        fetched: News | None,
        fetch_error: str | None,
    ) -> dict:
        """
        What the pipeline started from, field by field, and where each
        value came from: `supplied` by the caller, `extracted` from the
        page, or `missing`. A missing title or date is the thing this
        view exists to make visible - it silently weakens claim
        selection and the fact checker's subject restoration.
        """

        def origin(supplied, extracted) -> str:
            if supplied:
                return "supplied"
            if extracted:
                return "extracted"
            return "missing"

        return {
            "url": url,
            "fetched": fetched is not None,
            "error": fetch_error,
            "title": {
                "value": news.title,
                "origin": origin(title, fetched and fetched.title),
            },
            "author": {
                "value": news.author,
                "origin": origin(None, news.author),
            },
            "publishedAt": {
                "value": news.published_at.date().isoformat() if news.published_at else None,
                "origin": origin(None, news.published_at),
            },
            "imageUrl": news.image_url,
            "body": {
                "origin": origin(text, fetched),
                "length": len(news.content),
                "preview": news.content[:600],
            },
        }

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
