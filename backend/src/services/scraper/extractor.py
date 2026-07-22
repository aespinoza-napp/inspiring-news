from typing import Optional

from src.models.news import News
from src.models.source import NewsSource

from .strategies.trafilatura import TrafilaturaStrategy
from .strategies.beautifulsoup import BeautifulSoupStrategy
from .strategies.playwright_extraction import PlaywrightExtractionStrategy
from src.models.news import News

from .extraction_validator import ExtractionValidator

class ExtractorService:

    def __init__(self):

        self.strategies = [
            TrafilaturaStrategy(),
            #BeautifulSoupStrategy(),
            #PlaywrightExtractionStrategy()
        ]

    def extract(
        self,
        source: NewsSource,
        url: str,
    ) -> News | None:

        for strategy in self.strategies:

            extracted = strategy.extract(
                source,
                url,
            )

            if extracted is None:
                continue
            print(len(extracted.body))
            if not ExtractionValidator.is_valid(extracted):
                
                continue
            print("VALID")
            news = News(
                source_id=source.id,
                url=url,
                title=extracted.title,
                author=extracted.author,
                published_at=extracted.published_at,
                content=extracted.body,
                image_url=extracted.lead_image,
            )
            return news

        return None