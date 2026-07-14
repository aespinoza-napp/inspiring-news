"""
RSS discovery strategy.
"""
from __future__ import annotations

import feedparser

from src.models.source import NewsSource

from .base import DiscoveryStrategy


class RSSDiscoveryStrategy(DiscoveryStrategy):
    """Discover article URLs from an RSS feed."""

    ARTICLE_PATTERNS = (
        "/news/",
        "/article/",
        "/articles/",
        "/story/",
        "/stories/",
        "/world/",
        "/business/",
        "/politics/",
        "/technology/",
        "/science/",
        "/sport/",
        "/sports/",
        "/202",
    )

    def discover(
        self,
        source: NewsSource,
    ) -> list[str]:

        if not source.rss_url:
            return []

        feed = feedparser.parse(str(source.rss_url))

        urls = []

        for entry in feed.entries:

            link = getattr(entry, "link", None)

            if not link:
                continue

            if self._is_article(link):
                urls.append(link)

        return list(dict.fromkeys(urls))

    def _is_article(self, url: str) -> bool:
        return any(
            pattern in url.lower()
            for pattern in self.ARTICLE_PATTERNS
        )