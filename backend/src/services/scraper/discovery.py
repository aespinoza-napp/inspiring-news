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
    ) -> list[str]:

        for strategy in self.strategies:

            urls = strategy.discover(source)

            if urls:
                return urls

        return []