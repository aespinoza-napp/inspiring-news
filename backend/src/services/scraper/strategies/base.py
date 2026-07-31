from abc import ABC, abstractmethod

from src.models.scraper.extraction import ExtractionResult
from src.models.core.source import NewsSource

class DiscoveryStrategy(ABC):

    @abstractmethod
    def discover(
        self,
        source: NewsSource,
        topics: list[str],
    ) -> list[str]:
        ...


class ExtractionStrategy(ABC):

    @abstractmethod
    def extract(
        self,
        source: NewsSource,
        url: str,
    ) -> ExtractionResult | None:
        ...