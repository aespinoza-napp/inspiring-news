from src.models.source import NewsSource

from .base import DiscoveryStrategy


class RSSDiscoveryStrategy(DiscoveryStrategy):

    def discover(
        self,
        source: NewsSource,
    ) -> list[str]:

        if not source.rss_url:
            return []

        # feedparser.parse(...)
        # obtener urls

        return []