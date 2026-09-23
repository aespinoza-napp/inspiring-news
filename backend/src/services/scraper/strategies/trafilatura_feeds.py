"""
The fallback discovery step: trafilatura's own feed discovery, for
sources whose RSS feed cannot be read with feedparser.

feedparser needs well-formed XML. Three of the twelve configured feeds
are not (National Geographic, RTVE and SINC failed to parse in the
2026-09-23 check), and a source without an `rss_url` has nothing for it
to read at all. trafilatura reads feeds leniently and, given a homepage,
looks for the feeds the page advertises - so it is tried second, and
only when the configured feed produced nothing.

It returns URLs without titles or summaries, so the topic filter can
only look at the URL itself: the path's topic segments and the words in
its slug.
"""

from __future__ import annotations

from urllib.parse import urlsplit

import trafilatura.feeds

from src.models.core.source import NewsSource
from src.services.scraper.url_guard import check_url

from .rss import RSSDiscoveryStrategy


class TrafilaturaFeedDiscoveryStrategy(RSSDiscoveryStrategy):

    def discover(
        self,
        source: NewsSource,
        topics: list[str] = None,
    ) -> list[str]:

        # The configured feed first (it may only be malformed, which
        # trafilatura tolerates), then the homepage: four of the twelve
        # configured feed URLs had simply gone 404, and a site's homepage
        # advertises the feeds it actually publishes now.
        starts = list(dict.fromkeys(
            str(url) for url in (source.rss_url, source.base_url) if url
        ))

        links: list[str] = []

        for start in starts:

            # trafilatura fetches for itself; the start URL at least goes
            # through the guard. It comes from our own YAML, and the
            # article URLs it returns are guarded again when extracted.
            check_url(start)

            links = trafilatura.feeds.find_feed_urls(start)

            if links:
                break

        normalized_topics = {
            topic.lower().strip()
            for topic in (topics or [])
        }

        keywords = self._keywords_for(normalized_topics)
        url_patterns = self._url_patterns_for(normalized_topics)
        by_topic = self._filters_by_topic(source)

        urls = []

        for link in links:

            if not self._is_article(link):
                continue

            if not by_topic:
                urls.append(link)
                continue

            lowered = link.lower()
            slug = urlsplit(lowered).path.replace("-", " ").replace("_", " ")

            if any(pattern in lowered for pattern in url_patterns) or any(
                keyword in slug for keyword in keywords
            ):
                urls.append(link)

        return list(dict.fromkeys(urls))
