"""
Finding article URLs for a configured source, cheapest first.

1. The source's own RSS feed, read with feedparser - one request, and
   titles and summaries to filter on.
2. trafilatura's feed discovery - lenient with broken XML, and able to
   find a feed from the homepage - only when step 1 found nothing.
3. The source's topic section pages (/science/, /ciencia/...), read as
   HTML - only when there is no feed to be found at all. See
   strategies/topic_pages.py.

Every attempt is counted in the scraper stats under the purpose
`discovery`, so a feed that has started failing shows up on /scraper
next to the articles it no longer delivers.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime

from src.models.core.source import NewsSource
from src.services.scraper.fetcher import classify
from src.services.scraper.request_stats import Outcome, Purpose, RequestStats, request_stats

from .strategies.base import DiscoveryStrategy
from .strategies.rss import RSSDiscoveryStrategy
from .strategies.topic_pages import TopicPageDiscoveryStrategy
from .strategies.trafilatura_feeds import TrafilaturaFeedDiscoveryStrategy


@dataclass
class DiscoveryResult:

    urls: list[str] = field(default_factory=list)

    # The strategy that produced the URLs; None when none did.
    method: str | None = None

    tried: list[str] = field(default_factory=list)

    # The last failure, when every strategy came back empty or broken.
    error: str | None = None

    # URL -> when the feed says it was published, for the URLs whose
    # strategy knows (the RSS feed); the others have none.
    published: dict[str, datetime] = field(default_factory=dict)


class DiscoveryService:

    def __init__(
        self,
        strategies: list[DiscoveryStrategy] | None = None,
        stats: RequestStats | None = None,
    ):

        self.strategies = strategies if strategies is not None else [
            RSSDiscoveryStrategy(),
            TrafilaturaFeedDiscoveryStrategy(),
            TopicPageDiscoveryStrategy(),
        ]

        self.stats = stats if stats is not None else request_stats

    def discover(
        self,
        source: NewsSource,
        topics: list[str] = None,
    ) -> list[str]:

        return self.run(source, topics).urls

    def run(
        self,
        source: NewsSource,
        topics: list[str] = None,
    ) -> DiscoveryResult:

        result = DiscoveryResult()

        for strategy in self.strategies:

            name = type(strategy).__name__
            result.tried.append(name)

            started = time.perf_counter()
            status = None

            try:
                entries = _entries(strategy, source, topics)
                urls = [url for url, _ in entries]
                outcome = Outcome.OK if urls else Outcome.NO_CONTENT
                error = None if urls else "no matching article links"
            except Exception as exc:
                urls = []
                outcome, status, error = classify(exc)

            self.stats.record(
                str(source.rss_url or source.base_url),
                outcome,
                purpose=Purpose.DISCOVERY,
                strategy=name,
                source_id=source.id,
                status=status,
                error=error,
                elapsed_ms=(time.perf_counter() - started) * 1000,
                sent=0 if outcome == Outcome.BLOCKED else 1,
                tried=[name],
            )

            if urls:
                result.urls = urls
                result.method = name
                result.error = None
                result.published = {url: at for url, at in entries if at is not None}
                return result

            result.error = f"{name}: {error}"

        return result


def _entries(strategy: DiscoveryStrategy, source: NewsSource, topics) -> list[tuple[str, datetime | None]]:
    """(url, feed time) from a strategy that knows the times, (url, None) from one that does not."""

    if hasattr(strategy, "discover_entries"):
        return strategy.discover_entries(source=source, topics=topics)

    return [(url, None) for url in strategy.discover(source=source, topics=topics)]
