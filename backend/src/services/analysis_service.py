from logging import getLogger
from typing import Callable, Optional

from src.config.settings import settings
from src.config.thresholds import PipelineThresholds
from src.models.core.enriched_article import EnrichedArticle
from src.models.fact_checker.evidence import RejectedEvidence
from src.models.fact_checker.fact_check import FactCheck, Verdict
from src.models.fact_checker.fact_check_report import FactCheckReport
from src.models.fact_checker.pipeline_stage import PipelineStage
from src.models.core.news import News
from src.models.storage.lineage import DataLayer, RunContext
from src.models.storage.records import ProcessedRecord, RawRecord
from src.repositories.datalake_repository import DataLakeRepository, content_hash
from src.services.analysis_cache import AnalysisCache
from src.services.fact_checker.fact_checker import FactChecker
from src.services.fact_checker.retrieval.scraper import EvidenceScraper
from src.services.scraper.extractor import ExtractorService
from src.workflows.enrichment import NewsEnrichmentPipeline

logger = getLogger(__name__)

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
        lake: DataLakeRepository | None = None,
    ):
        self.fact_checker = fact_checker
        self.extractor = extractor or ExtractorService()
        self.enrichment_pipeline = enrichment_pipeline or NewsEnrichmentPipeline(settings)
        self.cache = cache or AnalysisCache()

        # `lake` has no default, like `fact_checker`: it is the only
        # other collaborator here that writes outside the process, and a
        # default would mean every test constructing an AnalysisService
        # silently wrote records into the real data directory. The app
        # passes the container singleton (see container.py); None simply
        # switches the persist stage off.
        self.lake = lake

    def analyze(
        self,
        url: str,
        force_refresh: bool = False,
        on_phase: Optional[OnPhase] = None,
        thresholds: PipelineThresholds | None = None,
    ) -> dict:
        """
        `thresholds` is the effective threshold set for this one run.
        None means "use the environment defaults" (settings.*), which is
        what PipelineThresholds() resolves to.
        """

        report_phase = on_phase or _noop

        thresholds = thresholds or PipelineThresholds()

        if not force_refresh:

            # Keyed by URL *and* thresholds: the same URL analysed with a
            # different admission threshold is a different result, and
            # serving the cached one would silently ignore the caller's
            # override.
            cached = self.cache.get(url, thresholds)

            if cached is not None:
                final = {**cached, "cached": True}
                report_phase("cache_hit", final)
                return final

        result = self._run_pipeline(url, report_phase, thresholds)

        final = {**result, "cached": False}

        if "error" in result:
            return final

        self.cache.set(url, result, thresholds)

        report_phase("done", final)

        return final

    def _run_pipeline(
        self,
        url: str,
        report_phase: OnPhase,
        thresholds: PipelineThresholds,
    ) -> dict:

        report_phase("scraping", {"url": url, "thresholds": thresholds.model_dump()})

        try:
            news = self.extractor.extract(
                EvidenceScraper.GENERIC_SOURCE,
                url,
                thresholds,
            )
        except Exception as exc:
            error = {"url": url, "error": f"Failed to fetch article: {exc}"}
            report_phase("failed", error)
            return error

        if news is None:
            error = {"url": url, "error": "Could not extract article content from this URL."}
            report_phase("failed", error)
            return error

        report_phase("scraped", {"title": news.title, "url": news.url})

        # Layer 1, immediately: what was extracted is worth keeping even
        # if every later stage fails.
        run = self._start_run(url, thresholds, report_phase)
        raw = self._store_raw(run, news, report_phase)

        report_phase("enriching", {})

        article = self.enrichment_pipeline.process(news, thresholds)

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

        # Layer 2, before fact-checking: the enrichment (metadata,
        # embedding) is durable from here on, so a SearXNG outage or an
        # LLM timeout during verification no longer throws away the whole
        # NLP pass.
        processed = self._store_processed(run, raw, article, report_phase)

        report = self.fact_checker.run(
            article,
            on_phase=report_phase,
            thresholds=thresholds,
        )

        # Layer 3, and the report attached back onto layer 2.
        storage = self._store_verified(
            run, raw, processed, article, report, report_phase
        )

        return {
            "url": url,
            "storage": storage,
            "thresholds": thresholds.model_dump(),
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

    # ------------------------------------------------------------------
    # Storage
    #
    # One write per stage, as that stage completes, rather than one write
    # of everything at the end:
    #
    #   extract  -> raw/
    #   enrich   -> processed/          (metadata + embedding)
    #   verify   -> exploitation/       (+ the report back onto processed)
    #
    # Every one of these is fail-soft and independent. Storage is a side
    # effect of analysis: a full disk must not discard a result that
    # already cost a scrape, an enrichment and one LLM call per claim.
    # Each failure is reported as its own phase event and logged, so it
    # is visible rather than silent, and a failure at one layer does not
    # stop the next from being written (the later record simply loses its
    # parent link).
    # ------------------------------------------------------------------

    def _start_run(
        self,
        url: str,
        thresholds: PipelineThresholds,
        report_phase: OnPhase,
    ) -> RunContext | None:

        if self.lake is None:
            return None

        try:
            return self.lake.start_run(url, thresholds)
        except Exception as exc:
            logger.warning("Could not start a lake run for %s", url, exc_info=True)
            report_phase("store_failed", {"layer": None, "error": str(exc)})
            return None

    def _store_raw(
        self,
        run: RunContext | None,
        news: News,
        report_phase: OnPhase,
    ) -> RawRecord | None:

        return self._store(
            run,
            DataLayer.RAW,
            report_phase,
            lambda: self.lake.persist_raw(run, news),
        )

    def _store_processed(
        self,
        run: RunContext | None,
        raw: RawRecord | None,
        article: EnrichedArticle,
        report_phase: OnPhase,
    ) -> ProcessedRecord | None:

        return self._store(
            run,
            DataLayer.PROCESSED,
            report_phase,
            lambda: self.lake.persist_processed(run, article, parent=raw),
        )

    def _store_verified(
        self,
        run: RunContext | None,
        raw: RawRecord | None,
        processed: ProcessedRecord | None,
        article: EnrichedArticle,
        report: FactCheckReport,
        report_phase: OnPhase,
    ) -> dict | None:
        """
        The verification stage's write. Two records, not one: the flat
        serving document in exploitation/, and the processed record
        rewritten with the report attached so the evidence and the
        rejected candidates - far too bulky for a serving document - stay
        in the layer meant to hold them.
        """

        # No lake configured at all -> no storage section in the result.
        # A lake that failed to open a run is a different thing, and must
        # not look like "storage is switched off": say so explicitly.
        if self.lake is None:
            return None

        if run is None:
            return {
                "persisted": False,
                "error": "Could not start a storage run; see the store_failed event.",
                "records": {layer.value: None for layer in DataLayer},
            }

        processed = self._store(
            run,
            DataLayer.PROCESSED,
            report_phase,
            lambda: self.lake.persist_processed(
                run, article, parent=raw, report=report
            ),
        ) or processed

        exploitation = self._store(
            run,
            DataLayer.EXPLOITATION,
            report_phase,
            lambda: self.lake.persist_exploitation(
                run, article, report=report, parent=processed
            ),
        )

        records = {
            DataLayer.RAW.value: raw.record_id if raw else None,
            DataLayer.PROCESSED.value: processed.record_id if processed else None,
            DataLayer.EXPLOITATION.value: (
                exploitation.record_id if exploitation else None
            ),
        }

        storage = {
            "persisted": all(records.values()),
            "runId": run.run_id,
            "contentHash": content_hash(article.body),
            "publishable": exploitation.publishable if exploitation else False,
            "records": records,
        }

        report_phase("stored", storage)

        return storage

    def _store(
        self,
        run: RunContext | None,
        layer: DataLayer,
        report_phase: OnPhase,
        write,
    ):

        if run is None or self.lake is None:
            return None

        report_phase("storing", {"layer": layer.value})

        try:
            record = write()
        except Exception as exc:
            logger.warning(
                "Failed to write the %s layer for run %s",
                layer.value,
                run.run_id,
                exc_info=True,
            )
            report_phase("store_failed", {"layer": layer.value, "error": str(exc)})
            return None

        report_phase(
            "stored_layer",
            {"layer": layer.value, "recordId": record.record_id},
        )

        return record

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
                    "evidence": [],
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
                "evidence": self._build_evidence(check),
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
                "evidence": [],
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
    def _build_evidence(check: FactCheck) -> list[dict]:

        cited = set(check.cited_evidence_indices)

        return [
            {
                "url": item.url,
                "title": item.title,
                "origin": item.origin,
                "relevanceScore": item.relevance_score,
                "sourceReliability": item.source_reliability,
                "publishedAt": item.published_at,
                "cited": index in cited,
            }
            for index, item in enumerate(check.evidence)
        ]

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
