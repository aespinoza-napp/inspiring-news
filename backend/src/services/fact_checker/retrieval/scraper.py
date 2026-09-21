from logging import getLogger

from src.config.settings import settings
from src.models.fact_checker.evidence import Evidence
from src.models.core.source import NewsSource, SourceType
from src.services.concurrency import SCRAPE, bounded_map
from src.services.scraper.extractor import ExtractorService

logger = getLogger(__name__)


class EvidenceScraper:
    """
    Fetches full-page text for web evidence by reusing ExtractorService
    rather than duplicating the scraping stack. ExtractorService.extract()
    requires a NewsSource; web-search hits don't have one, so a generic
    placeholder is synthesized purely to satisfy the interface - it is
    never persisted.
    """

    GENERIC_SOURCE = NewsSource(
        id="web",
        name="Web",
        base_url="https://example.com",
        source_type=SourceType.NEWS,
        reliability_index=0.5,
    )

    def __init__(self, extractor: ExtractorService | None = None):

        self.extractor = extractor or ExtractorService()

    def enrich(self, evidence: list[Evidence]) -> list[Evidence]:
        """
        Fetches every page at once, and returns them **in input order**.

        Order is not cosmetic here: the list that comes back is ranked,
        cut and then handed to the LLM as a numbered list it cites by
        index, so results in completion order would re-point every
        citation at a different source.

        This was the pipeline's longest non-LLM step - five pages fetched
        one after another, each waiting on a stranger's server. One slow
        host held up the other four for no reason.
        """

        return bounded_map(
            self._enrich_one,
            evidence,
            max_workers=settings.SCRAPE_MAX_CONCURRENCY,
            thread_name_prefix="evidence-scrape",
        )

    def _enrich_one(self, item: Evidence) -> Evidence:

        try:
            # Held around the fetch only. SCRAPE_MAX_CONCURRENCY is the
            # process-wide ceiling: bounded_map's fan-out is per claim,
            # and several claims (and several articles) reach here at
            # once - see src/services/concurrency.py.
            with SCRAPE.permit():
                news = self.extractor.extract(self.GENERIC_SOURCE, item.url)
        except Exception as exc:
            logger.warning("Failed to scrape evidence %s: %s", item.url, exc)
            return item

        if news is None:
            return item

        return item.model_copy(update={
            "content": news.content,
            "title": item.title or news.title or "",
            "published_at": item.published_at or news.published_at,
        })
