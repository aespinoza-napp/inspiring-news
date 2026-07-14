from src.models.source import NewsSource

from .strategies.rss import RSSDiscoveryStrategy
from .strategies.playwright_discover import PlaywrightDiscoveryStrategy


class DiscoveryService:

    def __init__(self):

        self.strategies = [
            RSSDiscoveryStrategy(),
            PlaywrightDiscoveryStrategy(),
        ]

    def discover(
        self,
        source: NewsSource,
        topics: list[str],
    ) -> list[str]:

        for strategy in self.strategies:

            urls = strategy.discover(
                source=source,
                topics=topics,
            )

            if urls:
                return urls

        return []