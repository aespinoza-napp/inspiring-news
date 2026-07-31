from src.config.settings import settings
from src.models.core.enriched_article import EnrichedArticle
from src.models.fact_checker.fact_check import Verdict
from src.models.fact_checker.fact_check_report import FactCheckReport
from src.services.fact_checker.fact_checker import FactChecker
from src.services.fact_checker.retrieval.scraper import EvidenceScraper
from src.services.scraper.extractor import ExtractorService
from src.workflows.enrichment import NewsEnrichmentPipeline

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
    ):
        self.fact_checker = fact_checker
        self.extractor = extractor or ExtractorService()
        self.enrichment_pipeline = enrichment_pipeline or NewsEnrichmentPipeline(settings)

    def analyze(self, url: str) -> dict:

        try:
            news = self.extractor.extract(EvidenceScraper.GENERIC_SOURCE, url)
        except Exception as exc:
            return {"url": url, "error": f"Failed to fetch article: {exc}"}

        if news is None:
            return {"url": url, "error": "Could not extract article content from this URL."}

        article = self.enrichment_pipeline.process(news)

        report = self.fact_checker.run(article)

        return {
            "url": url,
            "title": article.title,
            "keywords": article.keywords,
            "entities": article.entities,
            "topics": [topic.model_dump() for topic in (article.topics or [])],
            "claims": self._build_claims(article, report),
            "validity": {
                "isValid": report.validation_passed,
                "isDuplicate": report.duplicate,
                "hasTopic": report.topic_ok,
                "reasons": report.skipped_reason.split(",") if report.skipped_reason else [],
            },
            "factCheck": {
                "overallVerdict": report.overall_verdict,
                "overallConfidence": report.overall_confidence,
                "claimsTotal": report.claims_total,
                "claimsChecked": report.claims_selected,
            },
        }

    def _build_claims(
        self,
        article: EnrichedArticle,
        report: FactCheckReport,
    ) -> list[dict]:

        if report.claim_checks:

            checks = sorted(
                report.claim_checks,
                key=lambda check: _VERDICT_SEVERITY[check.verdict],
                reverse=True,
            )

            return [
                {
                    "text": check.claim,
                    "confidence": check.confidence,
                    "verdict": check.verdict,
                    "explanation": check.explanation,
                    "evidenceCount": check.evidence_count,
                }
                for check in checks
            ]

        # Validation failed (or nothing was selected for checking) - fall
        # back to the raw extracted claims so the UI still has something
        # to show, clearly unverified.
        return [
            {
                "text": claim.text,
                "confidence": claim.confidence,
                "verdict": None,
                "explanation": None,
                "evidenceCount": 0,
            }
            for claim in (article.claims or [])
        ]
