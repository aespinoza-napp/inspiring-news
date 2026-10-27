"""
Reading what is trending: the signals' feeds, a person's seed, and a
news search for the articles behind a trend (docs/decisions/trends.md).

Free by rule: every signal is a public feed read with no key, the search
is the project's own SearXNG with DuckDuckGo behind it (the fact-check's
SearxngClient), and TikTok is never scraped (seeds.py). Every feed goes
through the shared Fetcher - the URL guard, a timeout, redirects checked
hop by hop - and is counted on /scraper under the purpose "trends".

Nothing here fails a round. A signal that cannot be read is reported
with why; a search that cannot be answered leaves the trend with the
articles its signal gave, and a note saying so. Reddit and TikTok both
limit readers without a key: on 2026-10-26 Reddit's second request came
back empty and oEmbed answered "ratelimit triggered" after a few.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from logging import getLogger
from urllib.parse import quote

from src.config.settings import settings
from src.models.core.trend_signal import TrendSignal
from src.services.concurrency import bounded_map
from src.services.scraper.article_stats import comparable_url
from src.services.scraper.fetcher import Fetcher, classify
from src.services.scraper.request_stats import Outcome, RequestStats, request_stats
from src.services.search import SearchUnavailableError
from src.services.trends import readers, seeds
from src.services.trends.trends import Trend, TrendArticle, trend_id

logger = getLogger(__name__)

# Why these pages are fetched, as the scraper's request stats count them.
PURPOSE = "trends"

# Signals read at once: a handful of other people's servers, like the
# sources' feeds (ingestion_service.DISCOVERY_CONCURRENCY).
READ_CONCURRENCY = 4

# SearXNG's category shortcut, as the writer's related news uses it.
NEWS_BANG = "!news"

OEMBED = "https://www.tiktok.com/oembed?url="

SEED_SIGNAL = "seed"


@dataclass
class SignalRead:
    """One signal's read: its trends, or why there are none."""

    signal: TrendSignal

    trends: list[Trend] = field(default_factory=list)

    # Items that were not trends: a Reddit self-post, an untitled item.
    skipped: int = 0

    error: str | None = None

    elapsed_ms: int = 0

    def to_dict(self) -> dict:

        return {
            "signal": self.signal.id,
            "name": self.signal.name,
            "kind": self.signal.kind,
            "language": self.signal.language,
            "positive": self.signal.positive,
            "trends": len(self.trends),
            "articles": sum(len(trend.articles) for trend in self.trends),
            "skipped": self.skipped,
            "error": self.error,
            "elapsedMs": self.elapsed_ms,
        }


class TrendService:

    def __init__(
        self,
        signals: list[TrendSignal],
        fetcher: Fetcher | None = None,
        search=None,
        stats: RequestStats | None = None,
    ):
        self.signals = signals
        self.fetcher = fetcher or Fetcher()
        self.stats = stats if stats is not None else request_stats

        # Built on first use: most rounds never search.
        self._search = search

    @property
    def search(self):

        if self._search is None:
            from src.services.fact_checker.retrieval.search_provider import default_fallback
            from src.services.search import SearxngClient

            self._search = SearxngClient(fallback=default_fallback())

        return self._search

    def enabled_signals(self) -> list[TrendSignal]:

        return [signal for signal in self.signals if signal.enabled]

    def signals_for(self, signal_ids: list[str] | None = None) -> list[TrendSignal]:
        """The enabled signals, limited to `signal_ids` when given, in their configured order."""

        return [
            signal
            for signal in self.enabled_signals()
            if signal_ids is None or signal.id in signal_ids
        ]

    # ------------------------------------------------------------------
    # The signals
    # ------------------------------------------------------------------

    def read(self, signal_ids: list[str] | None = None) -> list[SignalRead]:
        """Every signal asked for, read at once; results in the signals' order (bounded_map)."""

        return bounded_map(
            self._read_one,
            self.signals_for(signal_ids),
            max_workers=READ_CONCURRENCY,
            thread_name_prefix="trends",
        )

    def _read_one(self, signal: TrendSignal) -> SignalRead:

        started = time.perf_counter()
        result = SignalRead(signal=signal)
        status = None

        try:
            page = self.fetcher.get(str(signal.url))
            status = page.status

            if signal.kind == "google_trends":
                result.trends = readers.read_google_trends(page.html, signal)
            else:
                result.trends, result.skipped = readers.read_ranked_feed(page.html, signal)

            outcome = Outcome.OK if result.trends else Outcome.NO_CONTENT

            if not result.trends:
                result.error = "the feed answered with no trends"

        except readers.FeedError as exc:
            outcome, result.error = Outcome.NO_CONTENT, str(exc)

        except Exception as exc:  # noqa: BLE001 - one signal, not the round
            outcome, status, result.error = classify(exc)

        result.elapsed_ms = round((time.perf_counter() - started) * 1000)

        if result.error:
            logger.warning("Trend signal %s: %s", signal.id, result.error)

        self.stats.record(
            str(signal.url),
            outcome,
            purpose=PURPOSE,
            strategy=signal.kind,
            source_id=signal.id,
            status=status,
            error=result.error,
            elapsed_ms=result.elapsed_ms,
            sent=0 if outcome == Outcome.BLOCKED else 1,
            tried=[signal.kind],
        )

        return result

    # ------------------------------------------------------------------
    # A person's seed
    # ------------------------------------------------------------------

    def seed(self, text: str, language: str | None = None) -> Trend:
        """
        A trend from what a person typed (seeds.py): the words or hashtags
        as its name, a TikTok link as its video, other links as its first
        articles. The video's caption is read through oEmbed, and names
        the trend when nothing else does. Raises seeds.SeedError when it
        names nothing to look for.
        """

        parsed = seeds.parse_seed(text)

        notes: list[str] = []
        video = None

        if parsed.tiktok:

            video = {
                "provider": "tiktok",
                "id": seeds.video_id(parsed.tiktok),
                "url": parsed.tiktok,
                "title": None,
                "author": None,
            }

            embedded = self._oembed(parsed.tiktok, notes)

            if embedded:
                video.update({key: value for key, value in embedded.items() if value})

        name = parsed.name or seeds.name_from((video or {}).get("title") or "")

        if not name and not parsed.links:
            raise seeds.SeedError(
                "There is nothing to search for: type the hashtag or a few words with the link"
                + (" (TikTok gave no caption for it)." if parsed.tiktok else ".")
            )

        name = name or parsed.links[0]

        return Trend(
            id=trend_id(SEED_SIGNAL, name),
            name=name,
            signal=SEED_SIGNAL,
            signal_name="Typed by a person",
            language=language,
            position=1,
            articles=[TrendArticle(url=link, found_by="seed") for link in parsed.links],
            video=video,
            seed=True,
            notes=notes,
        )

    def _oembed(self, link: str, notes: list[str]) -> dict | None:

        try:
            return readers.read_oembed(self.fetcher.get(OEMBED + quote(link, safe="")).html)
        except Exception as exc:  # noqa: BLE001 - the caption is a help, not the seed
            _, _, error = classify(exc)
            notes.append(f"TikTok's oEmbed did not answer ({error}); the video is kept by its link alone.")
            return None

    # ------------------------------------------------------------------
    # The articles behind a trend
    # ------------------------------------------------------------------

    def search_articles(self, trends: list[Trend], per_trend: int = 3) -> None:
        """
        Up to `per_trend` more articles for each trend, from a news search
        of its name in its language, appended after the signal's own and
        never repeating one (host and path compared). A search that cannot
        be answered leaves a note on the trend, not an error on the round.
        """

        if per_trend <= 0 or not trends:
            return

        found = bounded_map(
            lambda trend: self._search_one(trend, per_trend),
            trends,
            max_workers=settings.QUERY_MAX_CONCURRENCY,
            thread_name_prefix="trends-search",
        )

        for trend, articles in zip(trends, found):

            if isinstance(articles, str):
                trend.notes.append(articles)
                continue

            known = {comparable_url(article.url) for article in trend.articles}

            for article in articles:

                key = comparable_url(article.url)

                if key not in known:
                    known.add(key)
                    trend.articles.append(article)

    def _search_one(self, trend: Trend, per_trend: int) -> list[TrendArticle] | str:

        language = trend.language if trend.language in ("en", "es") else None

        try:
            answer = self.search.search(
                f"{NEWS_BANG} {trend.name}",
                max_results=max(per_trend * 2, settings.SEARXNG_MAX_RESULTS),
                language=language,
            )
        except SearchUnavailableError as exc:
            return f"The news search for this trend could not be answered ({exc}); it keeps its signal's articles."

        articles = []

        for item in answer:

            url = str(item.get("url") or "")

            # A search result is untrusted input: only web pages, titled.
            if not url.lower().startswith(("http://", "https://")) or not item.get("title"):
                continue

            articles.append(TrendArticle(
                url=url,
                title=readers.plain(item.get("title")),
                snippet=readers.plain(item.get("content"), readers.SNIPPET_CHARS),
                published=_published(item.get("publishedDate")),
                found_by="search",
            ))

            if len(articles) >= per_trend:
                break

        return articles


def _published(value) -> datetime | None:
    """A search result's ISO date as an aware time; None for nothing readable."""

    if not value or not isinstance(value, str):
        return None

    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
