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
        topics: list[str] = None,
    ) -> list[str]:

        if not source.rss_url:
            return []

        feed = feedparser.parse(str(source.rss_url))

        urls: list[str] = []

        normalized_topics = {
            topic.lower().strip()
            for topic in topics
        }

        for entry in feed.entries:

            link = getattr(entry, "link", None)

            if not link:
                continue

            if not self._is_article(link):
                continue

            if not self._matches_topics(entry, normalized_topics):
                continue

            urls.append(link)

        return list(dict.fromkeys(urls))

    def _matches_topics(
        self,
        entry,
        topics: set[str],
    ) -> bool:
        """
        Returns True if the RSS entry matches one of the requested topics.
        """

        title = getattr(entry, "title", "")
        summary = getattr(entry, "summary", "")

        categories = " ".join(
            tag.get("term", "")
            for tag in getattr(entry, "tags", [])
        )

        searchable = (
            f"{title} {summary} {categories}"
        ).lower()

        return any(
            topic in searchable
            for topic in topics
        )

    def _is_article(
        self,
        url: str,
    ) -> bool:

        url = url.lower()

        return any(
            pattern in url
            for pattern in self.ARTICLE_PATTERNS
        )