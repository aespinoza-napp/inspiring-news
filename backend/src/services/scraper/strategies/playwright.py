from typing import Optional

from src.models.news import News
from src.models.source import NewsSource

from .base import DiscoveryStrategy, ExtractionStrategy


class PlaywrightDiscoveryStrategy(DiscoveryStrategy):

    def discover(
        self,
        source: NewsSource,
    ) -> list[str]:

        # abrir homepage
        # buscar enlaces
        return []


class PlaywrightExtractionStrategy(ExtractionStrategy):

    def extract(
        self,
        source: NewsSource,
        url: str,
    ) -> Optional[News]:

        # usar playwright para páginas dinámicas

        return None