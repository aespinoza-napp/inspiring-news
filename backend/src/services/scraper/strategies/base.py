from abc import ABC, abstractmethod
from typing import Optional

from src.models.news import News
from src.models.source import NewsSource


class DiscoveryStrategy(ABC):

    @abstractmethod
    def discover(
        self,
        source: NewsSource,
    ) -> list[str]:
        ...


class ExtractionStrategy(ABC):

    @abstractmethod
    def extract(
        self,
        source: NewsSource,
        url: str,
    ) -> Optional[News]:
        ...