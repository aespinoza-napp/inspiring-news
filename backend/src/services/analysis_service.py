from typing import Callable, Optional

from src.config.settings import settings
from src.models.core.enriched_article import EnrichedArticle
from src.models.fact_checker.evidence import RejectedEvidence
from src.models.fact_checker.fact_check import Verdict
from src.models.fact_checker.fact_check_report import FactCheckReport
from src.models.fact_checker.pipeline_stage import PipelineStage
from src.services.analysis_cache import AnalysisCache
from src.services.fact_checker.fact_checker import FactChecker
from src.services.fact_checker.retrieval.scraper import EvidenceScraper
from src.services.scraper.extractor import ExtractorService
from src.workflows.enrichment import NewsEnrichmentPipeline

OnPhase = Callable[[str, dict], None]


def _noop(phase: str, data: dict) -> None:
    pass

_VERDICT_SEVERITY = {
    Verdict.TRUE: 0,
    Verdict.UNVERIFIED: 1,
    Verdict.MISLEADING: 2,
    Verdict.FALSE: 3,
}


class AnalysisService:
    """
    Runs a single arbitrary URL through the full pipeline: scrape -> enrich
    -> validate -> fact-check, and shapes the result for the frontend.

    Results are cached by URL (see AnalysisCache) - a repeat request for
    the same URL returns the stored result instead of re-scraping and
    re-running a real SearXNG search + LLM call per claim. Pass
    force_refresh=True to bypass the cache and re-run the pipeline.

    `fact_checker` has no default: it owns a VectorRepository backed by a
    single-process Qdrant client, and this app must only ever have one of
    those (opening a second one against the same on-disk collection can
    fail to acquire the storage lock) - it's expected to come from the
    shared container singleton, not be constructed ad hoc per request.
    """

    def __init__(
        self,
        fact_checker: FactChecker,
        extractor: ExtractorService | None = None,
        enrichment_pipeline: NewsEnrichmentPipeline | None = None,
        cache: AnalysisCache | None = None,
    ):
        self.fact_checker = fact_checker
        self.extractor = extractor or ExtractorService()
        self.enrichment_pipeline = enrichment_pipeline or NewsEnrichmentPipeline(settings)
        self.cache = cache or AnalysisCache()

    def analyze(
        self,
        url: str,
        force_refresh: bool = False,
        on_phase: Optional[OnPhase] = None,
    ) -> dict:

        report_phase = on_phase or _noop

        if not force_refresh:

            cached = self.cache.get(url)

            if cached is not None:
                final = {**cached, "cached": True}
                report_phase("cache_hit", final)
                return final

        result = self._run_pipeline(url, report_phase)

        final = {**result, "cached": False}

        if "error" in result:
            return final

        self.cache.set(url, result)

        report_phase("done", final)

        return final

    def _run_pipeline(self, url: str, report_phase: OnPhase) -> dict:

        report_phase("scraping", {"url": url})

        try:
            news = self.extractor.extract(EvidenceScraper.GENERIC_SOURCE, url)
        except Exception as exc:
            error = {"url": url, "error": f"Failed to fetch article: {exc}"}
            report_phase("failed", error)
            return error

        if news is None:
            error = {"url": url, "error": "Could not extract article content from this URL."}
            report_phase("failed", error)
            return error

        report_phase("scraped", {"title": news.title, "url": news.url})

        report_phase("enriching", {})

        article = self.enrichment_pipeline.process(news)

        topics = [topic.model_dump() for topic in (article.topics or [])]
        sentiment = self._build_sentiment(article)
        quality = self._build_quality(article)

        report_phase("enriched", {
            "title": article.title,
            "keywords": article.keywords,
            "entities": article.entities,
            "topics": topics,
            "sentiment": sentiment,
            "quality": quality,
        })

        report = self.fact_checker.run(article, on_phase=report_phase)

        return {
            "url": url,
            "title": article.title,
            "keywords": article.keywords,
            "entities": article.entities,
            "topics": topics,
            "sentiment": sentiment,
            "quality": quality,
            "claims": self._build_claims(article, report),
            "validity": {
                "isValid": report.validation_passed,
                "isDuplicate": report.duplicate,
                "hasTopic": report.topic_ok,
                "reasons": report.skipped_reason.split(",") if report.skipped_reason else [],
                "impactScore": report.impact_score,
                "impactReasons": report.impact_reasons,
                "failedStage": report.failed_stage,
            },
            "factCheck": {
                "overallVerdict": report.overall_verdict,
                "overallConfidence": report.overall_confidence,
                "claimsTotal": report.claims_total,
                "claimsChecked": report.claims_selected,
            },
        }

    @staticmethod
    def _build_sentiment(article: EnrichedArticle) -> dict:

        sentiment = article.sentiment

        return {
            "label": sentiment.label,
            "positive": sentiment.positive,
            "neutral": sentiment.neutral,
            "negative": sentiment.negative,
            "polarity": sentiment.polarity,
            "subjectivity": sentiment.subjectivity,
            "confidence": sentiment.confidence,
            "emotionalIntensity": sentiment.emotional_intensity,
        }

    @staticmethod
    def _build_quality(article: EnrichedArticle) -> dict:

        quality = article.quality

        return {
            "readability": quality.readability,
            "objectivity": quality.objectivity,
            "constructiveness": quality.constructiveness,
            "inspirationalScore": quality.inspirational_score,
            "hopefulness": quality.hopefulness,
            "societalImpact": quality.societal_impact,
            "novelty": quality.novelty,
        }

    def _build_claims(
        self,
        article: EnrichedArticle,
        report: FactCheckReport,
    ) -> list[dict]:

        if not report.validation_passed:

            # The article never got past the admission filter, so nothing
            # was selected or checked - show the raw extracted claims,
            # all tagged as having failed at that first gate.
            return [
                {
                    "text": claim.text,
                    "confidence": claim.confidence,
                    "verdict": None,
                    "explanation": None,
                    "evidenceCount": 0,
                    "rejectedSources": [],
                    "reachedStage": PipelineStage.ADMISSION_FILTER,
                    "stageNote": report.skipped_reason,
                    "rawVerdict": None,
                    "rawConfidence": None,
                }
                for claim in (article.claims or [])
            ]

        checks = sorted(
            report.claim_checks,
            key=lambda check: _VERDICT_SEVERITY[check.verdict],
            reverse=True,
        )

        checked = [
            {
                "text": check.claim,
                "confidence": check.confidence,
                "verdict": check.verdict,
                "explanation": check.explanation,
                "evidenceCount": check.evidence_count,
                "rejectedSources": self._build_rejected_sources(check.rejected_sources),
                "reachedStage": check.reached_stage,
                "stageNote": check.stage_note,
                "rawVerdict": check.raw_verdict,
                "rawConfidence": check.raw_confidence,
            }
            for check in checks
        ]

        unselected = [
            {
                "text": rejected.text,
                "confidence": rejected.confidence,
                "verdict": None,
                "explanation": None,
                "evidenceCount": 0,
                "rejectedSources": [],
                "reachedStage": PipelineStage.CLAIM_SELECTION,
                "stageNote": rejected.reason,
                "rawVerdict": None,
                "rawConfidence": None,
            }
            for rejected in report.unselected_claims
        ]

        return checked + unselected

    @staticmethod
    def _build_rejected_sources(sources: list[RejectedEvidence]) -> list[dict]:

        return [
            {
                "url": source.url,
                "title": source.title,
                "origin": source.origin,
                "stage": source.stage,
                "reason": source.reason,
                "score": source.score,
            }
            for source in sources
        ]
