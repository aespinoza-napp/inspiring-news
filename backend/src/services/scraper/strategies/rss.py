"""
RSS discovery strategy.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

import feedparser

from src.models.core.source import NewsSource
from src.services.scraper.fetcher import Fetcher
from src.config.topic_url_patterns import TOPIC_URL_PATTERNS
from src.config.topics import TOPICS
from .base import DiscoveryStrategy


# A date in the path is the most language-independent sign of an article:
# /2026/09/23/, /2026-09-23/, /20260923/.
DATED_PATH = re.compile(r"/(20\d{2})[/-]?(0[1-9]|1[0-2])[/-]?(0[1-9]|[12]\d|3[01])(/|$|-)")

# A slug this many words long is a headline, not a section name.
MIN_SLUG_WORDS = 4

# The language TOPICS' keywords are written in. Matching them against a
# feed in another language filters at random - see _filters_by_topic.
KEYWORD_LANGUAGE = "en"


class RSSDiscoveryStrategy(DiscoveryStrategy):
    """Discover article URLs from an RSS feed."""

    ARTICLE_PATTERNS = (
        "/article/",
        "/articles/",
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

    def __init__(self, fetcher: Fetcher | None = None):

        # The feed is fetched here, not by feedparser: feedparser's own
        # HTTP has no timeout (a dead feed held discovery for 20s+ in the
        # live check) and bypasses the URL guard.
        self.fetcher = fetcher or Fetcher()

    def discover(
        self,
        source: NewsSource,
        topics: list[str] = None,
    ) -> list[str]:

        if not source.rss_url:
            return []

        feed = feedparser.parse(self.fetcher.get(str(source.rss_url)).html)

        urls: list[str] = []

        normalized_topics = {
            topic.lower().strip()
            for topic in (topics or [])
        }

        keywords = self._keywords_for(normalized_topics)
        url_patterns = self._url_patterns_for(normalized_topics)
        by_topic = self._filters_by_topic(source)

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

            if by_topic and not matches_url and not self._matches_keywords(entry, keywords):
                continue

            urls.append(link)

        return list(dict.fromkeys(urls))

    @staticmethod
    def _filters_by_topic(source: NewsSource) -> bool:
        """
        Whether the keyword pre-filter can say anything about this
        source. Every TOPICS keyword is English, so against a Spanish feed
        it matched almost nothing and dropped articles at random (El País:
        149 entries, 5 kept). For those sources discovery keeps every
        article-shaped link and leaves topic to the admission filter,
        which rejects before any LLM call - a scrape and an enrichment
        each, not a fact-check.
        """

        return (source.language or KEYWORD_LANGUAGE).lower()[:2] == KEYWORD_LANGUAGE

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

        Video pages are rejected outright, even if their path also
        contains an article-shaped segment. Some sources (e.g. CNN)
        nest video URLs under the same category segments as real
        articles (.../videos/world/...), so an unqualified substring
        match on "/world/" would let a video page through - and video
        pages extract as player/caption UI chrome, not article prose,
        which produced nonsense "claims" downstream (verified live:
        ClaimExtractor scored a caption fragment like "3:05 �
        Source:" at 0.90 confidence).
        """

        url = url.lower()

        if "/video/" in url or "/videos/" in url:
            return False

        path = urlsplit(url).path

        # The English section names above missed nearly every Spanish
        # article (El Mundo 26 of 26, La Vanguardia 130 of 132) and every
        # NASA one. A date in the path or a headline-length slug says
        # "article" in any language; a homepage or a section index has
        # neither.
        slug = re.sub(r"\.html?$", "", path.rstrip("/").rsplit("/", 1)[-1])

        return (
            any(pattern in url for pattern in self.ARTICLE_PATTERNS)
            or any(pattern in url for pattern in self._ALL_TOPIC_URL_PATTERNS)
            or bool(DATED_PATH.search(path))
            or len([word for word in re.split(r"[-_]", slug) if word]) >= MIN_SLUG_WORDS
        )