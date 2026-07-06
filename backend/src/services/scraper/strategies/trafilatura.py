from typing import Optional

from src.models.news import News
from src.models.source import NewsSource

from .base import ExtractionStrategy


class TrafilaturaStrategy(ExtractionStrategy):

    def extract(
        self,
        source: NewsSource,
        url: str,
    ) -> Optional[News]:

        # descargar html
        # trafilatura.extract()

        return None