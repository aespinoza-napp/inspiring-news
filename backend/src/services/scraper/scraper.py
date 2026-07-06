from typing import Optional

from src.models.news import News
from src.models.source import NewsSource

from .discovery import DiscoveryService
from .extractor import ExtractorService


class Scraper:
    """
    High level scraper orchestrator.
    """

    def __init__(self):
        self.discovery = DiscoveryService()
        self.extractor = ExtractorService()

    def discover(
        self,
        source: NewsSource,
    ) -> list[str]:
        return self.discovery.discover(source)

    def extract(
        self,
        source: NewsSource,
        url: str,
    ) -> Optional[News]:
        return self.extractor.extract(source, url)