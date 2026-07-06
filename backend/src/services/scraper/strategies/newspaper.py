from typing import Optional

from src.models.news import News
from src.models.source import NewsSource

from .base import ExtractionStrategy


class NewspaperStrategy(ExtractionStrategy):

    def extract(
        self,
        source: NewsSource,
        url: str,
    ) -> Optional[News]:

        # newspaper3k.Article

        return None