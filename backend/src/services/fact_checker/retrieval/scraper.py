from logging import getLogger

from src.models.evidence import Evidence
from src.models.source import NewsSource, SourceType
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

        return [self._enrich_one(item) for item in evidence]

    def _enrich_one(self, item: Evidence) -> Evidence:

        try:
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
