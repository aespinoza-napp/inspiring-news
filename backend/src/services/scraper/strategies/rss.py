"""
RSS discovery strategy.
"""
from __future__ import annotations

import feedparser

from src.models.core.source import NewsSource
from src.config.topic_url_patterns import TOPIC_URL_PATTERNS
from src.config.topics import TOPICS
from .base import DiscoveryStrategy


class RSSDiscoveryStrategy(DiscoveryStrategy):
    """Discover article URLs from an RSS feed."""

    ARTICLE_PATTERNS = (
        "/story/",
        "/stories/",
        "/world/",
        "/technology/",
        "/tech/",
        "/science/",
        "/health/",
        "/environment/",
        "/climate/",
        "/culture/",
        "/travel/",
        "/food/",
        "/sport/",
        "/sports/",
        "/features/",
        "/feature/",
        "/latest/",
        "/live/"
    )

    _ALL_TOPIC_URL_PATTERNS = {
        pattern
        for patterns in TOPIC_URL_PATTERNS.values()
        for pattern in patterns
    }

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

        keywords = self._keywords_for(normalized_topics)
        url_patterns = self._url_patterns_for(normalized_topics)

        for entry in feed.entries:

            link = getattr(entry, "link", None)

            if not link:
                continue

            if not self._is_article(link):
                continue

            matches_url = any(
                pattern in link.lower()
                for pattern in url_patterns
            )

            if not matches_url and not self._matches_keywords(entry, keywords):
                continue

            urls.append(link)

        return list(dict.fromkeys(urls))

    def _keywords_for(self, topics: set[str]) -> set[str]:
        """
        Expands topic ids (e.g. "space") into their configured keyword
        vocabulary (e.g. "nasa", "mars", ...). Matching the bare topic id
        against article text is unreliable - the id itself rarely appears
        verbatim in a title or summary.
        """

        return {
            keyword.lower()
            for topic in topics
            if topic in TOPICS
            for keyword in TOPICS[topic].keywords
        }

    def _url_patterns_for(self, topics: set[str]) -> set[str]:

        return {
            pattern
            for topic in topics
            for pattern in TOPIC_URL_PATTERNS.get(topic, ())
        }

    def _matches_keywords(
        self,
        entry,
        keywords: set[str],
    ) -> bool:
        """
        Returns True if the RSS entry's title/summary/categories mention
        one of the requested topics' keywords.
        """

        if not keywords:
            return False

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
            keyword in searchable
            for keyword in keywords
        )

    def _is_article(
        self,
        url: str,
    ) -> bool:
        """
        A link "looks like" an article if its path matches one of the
        generic article patterns, or one of the topic-specific URL
        patterns from any configured topic (a "/space/" or "/medicine/"
        segment is essentially always an article, not a homepage/about
        page - regardless of which topic the caller currently asked for).
        """

        url = url.lower()

        return any(
            pattern in url
            for pattern in self.ARTICLE_PATTERNS
        ) or any(
            pattern in url
            for pattern in self._ALL_TOPIC_URL_PATTERNS
        )