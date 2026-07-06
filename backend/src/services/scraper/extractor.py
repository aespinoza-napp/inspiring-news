from typing import Optional

from src.models.news import News
from src.models.source import NewsSource

from .strategies.trafilatura import TrafilaturaStrategy
from .strategies.newspaper import NewspaperStrategy
from .strategies.beautifulsoup import BeautifulSoupStrategy


class ExtractorService:

    def __init__(self):

        self.strategies = [
            TrafilaturaStrategy(),
            NewspaperStrategy(),
            BeautifulSoupStrategy(),
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