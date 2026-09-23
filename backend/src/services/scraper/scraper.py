from typing import Optional

from src.config.topics import TOPICS
from src.models.core.news import News
from src.models.core.source import NewsSource

from .discovery import DiscoveryService
from .extractor import ExtractorService
from .request_stats import Purpose


class Scraper:
    """
    Discovery and extraction for a configured source, side by side.

    Ingestion (src/services/ingestion_service.py) uses DiscoveryService
    directly and hands each new URL to the analysis pipeline, which does
    its own extraction; this is the convenience pairing for callers that
    want the two steps without the rest of the pipeline.
    """

    def __init__(self):

        self.discovery = DiscoveryService()
        self.extractor = ExtractorService()

    def discover(
        self,
        source: NewsSource,
        topics: list[str] | None = None,
    ) -> list[str]:

        # Topic ids, as declared. This used to pass the TOPICS dict itself,
        # which only worked because iterating a dict yields its keys.
        return self.discovery.discover(
            source=source,
            topics=topics if topics is not None else list(TOPICS),
        )

    def extract(
        self,
        source: NewsSource,
        url: str,
    ) -> Optional[News]:

        # No `topics` argument any more: it was accepted and ignored.
        # Topic filtering happens at discovery, where it saves a fetch.
        return self.extractor.extract(source, url, purpose=Purpose.INGESTION)
