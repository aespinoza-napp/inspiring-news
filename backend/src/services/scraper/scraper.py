from typing import Optional

from src.config.topics import TOPICS
from src.models.core.news import News
from src.models.core.source import NewsSource

from .discovery import DiscoveryService
from .extractor import ExtractorService


class Scraper:

    def __init__(self):

        self.discovery = DiscoveryService()
        self.extractor = ExtractorService()

    def discover(
        self,
        source: NewsSource,
        topics: list[str] | None = None,
    ) -> list[str]:

        return self.discovery.discover(
            source=source,
            topics=topics or TOPICS,
        )

    def extract(
        self,
        source: NewsSource,
        url: str,
        topics: list[str] | None = None,
    ) -> Optional[News]:

        return self.extractor.extract(source, url)