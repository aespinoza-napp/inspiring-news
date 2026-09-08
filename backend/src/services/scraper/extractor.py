from typing import Optional

from src.config.thresholds import PipelineThresholds
from src.models.core.news import News
from src.models.core.source import NewsSource

from .strategies.trafilatura import TrafilaturaStrategy
from .strategies.beautifulsoup import BeautifulSoupStrategy
from .strategies.playwright_extraction import PlaywrightExtractionStrategy
from src.models.core.news import News

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
        thresholds: PipelineThresholds | None = None,
    ) -> News | None:

        for strategy in self.strategies:

            extracted = strategy.extract(
                source,
                url,
            )

            if extracted is None:
                continue

            if not ExtractionValidator.is_valid(extracted, thresholds):
                continue

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