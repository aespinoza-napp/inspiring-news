from abc import ABC, abstractmethod

from src.models.news import News


class NewsRepository(ABC):
    """Abstract repository interface."""

    @abstractmethod
    def save(self, news: News) -> None:
        pass

    @abstractmethod
    def load(self, news_id: str) -> News:
        pass

    @abstractmethod
    def list(self) -> list[News]:
        pass