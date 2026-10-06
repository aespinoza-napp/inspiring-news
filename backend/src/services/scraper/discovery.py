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
from datetime import datetime, timedelta, timezone

from src.models.core.source import NewsSource
from src.services.scraper.fetcher import classify
from src.services.scraper.request_stats import Outcome, Purpose, RequestStats, request_stats

from .strategies.base import DiscoveryStrategy
from .strategies.rss import DiscoveredLink, RSSDiscoveryStrategy, date_from_url
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

    # URL -> {"title", "summary"} from the feed item, for the URLs whose
    # strategy reads a feed. What the candidate list shows and the AI
    # selection reads before any article page is fetched.
    details: dict[str, dict] = field(default_factory=dict)

    # Items the strategy found but dropped as older than max_age.
    stale: int = 0


class DiscoveryService:

    def __init__(
        self,
        strategies: list[DiscoveryStrategy] | None = None,
        stats: RequestStats | None = None,
        max_age: timedelta | None = None,
    ):

        self.strategies = strategies if strategies is not None else [
            RSSDiscoveryStrategy(),
            TrafilaturaFeedDiscoveryStrategy(),
            TopicPageDiscoveryStrategy(),
        ]

        self.stats = stats if stats is not None else request_stats

        # Items older than this are dropped - by the feed's time, or the
        # date in the link's own path (date_from_url) when there is no
        # feed; None keeps everything. Items dated neither way stay: a
        # missing date is not an old one. A feed
        # with nothing newer counts as empty, so the next step is tried:
        # RTVE's feed has carried only June 2022 items since then, and a
        # 2026-10-06 Culture round listed two of them (a tanker crash on
        # the AP-7 among them).
        self.max_age = max_age

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

            stale = 0

            try:
                found = _items(strategy, source, topics)
                items = self._recent(found)
                stale = len(found) - len(items)
                urls = [item.url for item in items]
                outcome = Outcome.OK if urls else Outcome.NO_CONTENT
                error = None if urls else _nothing_found(found, self.max_age)
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
                result.published = {item.url: item.published for item in items if item.published is not None}
                result.details = {
                    item.url: {"title": item.title, "summary": item.summary}
                    for item in items
                    if item.title or item.summary
                }
                result.stale = stale
                return result

            result.error = f"{name}: {error}"

        return result

    def _recent(self, items: list[DiscoveredLink]) -> list[DiscoveredLink]:

        if self.max_age is None:
            return items

        oldest = datetime.now(timezone.utc) - self.max_age

        return [item for item in items if (when := _dated(item)) is None or when >= oldest]


def _dated(item: DiscoveredLink) -> datetime | None:
    """
    The feed's time, or failing it the date the link carries in its path:
    ABC's section pages listed a mortgage calculator stamped 2026-05-25 as
    news on 2026-10-06. Neither: undated, and kept.
    """

    return item.published or date_from_url(item.url)


def _nothing_found(found: list[DiscoveredLink], max_age: timedelta | None) -> str:

    if not found:
        return "no matching article links"

    newest = max(when for when in map(_dated, found) if when is not None)

    return f"only items older than {max_age.days} days (newest {newest.date().isoformat()})"


def _items(strategy: DiscoveryStrategy, source: NewsSource, topics) -> list[DiscoveredLink]:
    """
    Each link as a DiscoveredLink: with its feed time, title and summary
    from a strategy that reads a feed, with the URL alone from one that
    does not.
    """

    if hasattr(strategy, "discover_items"):
        return strategy.discover_items(source=source, topics=topics)

    if hasattr(strategy, "discover_entries"):
        return [
            DiscoveredLink(url=url, published=at)
            for url, at in strategy.discover_entries(source=source, topics=topics)
        ]

    return [DiscoveredLink(url=url) for url in strategy.discover(source=source, topics=topics)]
