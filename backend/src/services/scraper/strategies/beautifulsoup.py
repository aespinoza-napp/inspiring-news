from typing import Optional

from src.models.news import News
from src.models.source import NewsSource

from .base import ExtractionStrategy


class BeautifulSoupStrategy(ExtractionStrategy):

    def extract(
        self,
        source: NewsSource,
        url: str,
    ) -> Optional[News]:

        # requests
        # BeautifulSoup
        # selectores css personalizados

        return None