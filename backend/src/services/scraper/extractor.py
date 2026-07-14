from typing import Optional

from src.models.news import News
from src.models.source import NewsSource

from .strategies.trafilatura import TrafilaturaStrategy
from .strategies.newspaper import NewspaperStrategy
from .strategies.beautifulsoup import BeautifulSoupStrategy
from .strategies.playwright_extraction import PlaywrightExtractionStrategy


class ExtractorService:

    def __init__(self):

        self.strategies = [
            TrafilaturaStrategy(),
            NewspaperStrategy(),
            BeautifulSoupStrategy(),
            PlaywrightExtractionStrategy()
        ]

    def extract(
        self,
        source: NewsSource,
        url: str,
    ) -> Optional[News]:

        for strategy in self.strategies:

            article = strategy.extract(source, url)

            if article:
                return article

        return None