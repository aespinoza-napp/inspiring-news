"""
A trending round: what is spreading right now, as candidates for
/discover (docs/decisions/trends.md, "The lens").

The person sees a new topic, Trending, beside the five groups. Underneath
it is a way in, not a sixth group: virality is how a story travels and
says nothing about what it is about - a viral koala rescue is still
Nature - and as a group it would fight the code (GROUP_FIT would list the
best viral stories last as "of another group", and the labeller's copy of
the groups and the evaluation's balance over five would change).

A round reads the trend signals (services/trends/trend_service.py) and a
person's seed, and offers each trend's articles the way discovery offers
a source's links, through the same filters, the same mission screen and
the same ranking with one part changed:

1. **What a link must pass**: article shape, no off-mission section, live
   page or betting site (strategies/rss.py `off_mission`), not already in
   the lake, each URL once - the first trend to bring it keeps it.
2. **Age**: the trend must have started within MAX_TREND_AGE, its articles
   within MAX_ARTICLE_AGE, by their own time or the date in their path.
3. **The mission screen**, unchanged, over every article that passed; no
   signal is exempt, not even a positive one (r/UpliftingNews carried an
   election result on 2026-10-26). It is what removes the TV, the sport,
   the crashes and the celebrities that most trends are.
4. **At most `per_trend` articles a trend**, after the screen: one trend's
   articles are one story, and the ranking's SAME_STORY lists the second
   after every distinct story.
5. **The ranking** (selection/ranking.py `trend_rank`): the story's 0.6
   as in any round (topic emphasis only when groups were picked), the
   signal's record in this round's screen in the source's place, virality
   in reliability's.

Nothing here judges anything an analysis does: a chosen article is an
ordinary analysis job, and its trend is only remembered for the writing
flow (services/trends/ledger.py).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from logging import getLogger

from src.services.ingestion_service import IngestionService, title_from_url, topics_for
from src.services.scraper.article_stats import comparable_url
from src.services.scraper.request_stats import domain_of
from src.services.scraper.strategies.rss import RSSDiscoveryStrategy, article_shaped, date_from_url, off_mission
from src.services.selection import ranking
from src.services.selection.mission_screen import MARGIN, MARGINS, Candidate, Reading
from src.services.trends.trend_service import SEED_SIGNAL, SignalRead, TrendService
from src.services.trends.trends import Trend, TrendArticle

logger = getLogger(__name__)

# A trend that started rising longer ago than this is not trending. Google
# lists a search for about a day; a subreddit's top of the day is a day's;
# an outlet's feed runs back weeks.
MAX_TREND_AGE = timedelta(hours=72)

# Its articles may be older than the trend: the story often broke before it
# trended. Google attached ABC's piece on Netflix's La Regenta, dated 23 Oct,
# to the search that rose on 26 Oct. A week keeps that and drops a 2016 post
# (r/UpliftingNews' Dolly Parton link, dated in its path).
MAX_ARTICLE_AGE = timedelta(days=7)

# Articles kept per trend after the screen, by default and at most.
PER_TREND = 2
MAX_PER_TREND = 5

# The seed's own search, when it brings no article of its own.
SEED_SEARCH = 4

LENS = "trending"

# Shape only: RSSDiscoveryStrategy._is_article reads no feed, and the
# strategy's fetcher is never used here.
_SHAPE = RSSDiscoveryStrategy()


def looks_like_article(url: str) -> bool:
    """An article by its own shape, or by the sections an article sits in (the feed step's rule)."""

    return article_shaped(url) or _SHAPE._is_article(url)


def virality(trends: list[Trend]) -> dict[str, float]:
    """
    Each trend's place among its own signal's trends, in [0, 1]: 1 for the
    signal's top trend, 0 for its last, ties sharing their average place.
    By approximate searches where the signal gives them (Google), else by
    the feed's order (a subreddit's votes, an outlet's newest). A trend
    typed by a person has none. Within a signal, so a 200-search Spanish
    trend and a subreddit's tenth post are each judged against their own.
    """

    by_signal: dict[str, list[Trend]] = defaultdict(list)

    for trend in trends:
        if not trend.seed:
            by_signal[trend.signal].append(trend)

    values: dict[str, float] = {}

    for members in by_signal.values():

        if len(members) == 1:
            values[members[0].id] = 1.0
            continue

        if any(member.traffic is not None for member in members):
            keys = [-(member.traffic or 0) for member in members]
        else:
            keys = [member.position for member in members]

        ordered = sorted(keys)
        last = len(members) - 1

        for member, key in zip(members, keys):
            first = ordered.index(key)
            tied = ordered.count(key)
            place = first + (tied - 1) / 2
            values[member.id] = round(1.0 - place / last, 4)

    return values


@dataclass
class _Offered:
    """One article that passed the link filters, on its way to the screen."""

    trend: Trend

    article: TrendArticle

    title: str

    title_from: str


@dataclass
class _Row:
    """What a round says about one signal (or the seed): the sources table's columns."""

    source: str

    name: str

    language: str | None

    method: str

    trends: int = 0

    skipped: int = 0

    discovered: int = 0

    already_stored: int = 0

    not_articles: int = 0

    stale: int = 0

    judged: int = 0

    screened: int = 0

    candidates: int = 0

    deferred: int = 0

    error: str | None = None

    def to_dict(self) -> dict:

        return {
            "source": self.source,
            "name": self.name,
            "language": self.language,
            "method": self.method,
            "trends": self.trends,
            "skipped": self.skipped,
            "discovered": self.discovered,
            "alreadyStored": self.already_stored,
            "notArticles": self.not_articles,
            "candidates": self.candidates,
            "deferred": self.deferred,
            "judged": self.judged,
            "screened": self.screened,
            "stale": self.stale,
            "error": self.error,
        }


@dataclass
class _TrendTally:

    articles: int = 0

    candidates: int = 0

    screened: int = 0

    stale: bool = False


class TrendingDiscovery:

    def __init__(self, ingestion: IngestionService, trends: TrendService):

        # The ingestion service's lake, screen and sightings: one of each
        # per process, shared with the topic rounds.
        self.ingestion = ingestion
        self.trends = trends

    def discover(
        self,
        groups: list[str] | None = None,
        signal_ids: list[str] | None = None,
        seed: str | None = None,
        per_trend: int = PER_TREND,
        search: bool = False,
        topic_emphasis: float | None = None,
        now: datetime | None = None,
        edition: str = "positive",
    ) -> dict:
        """
        A round of candidates from what is trending: the signals in
        `signal_ids` (None: every enabled one; []: none, for a seed alone)
        and a person's `seed`, best first. `search` also looks each
        signal's trend up in the news; a seed is always looked up.
        `groups`, when given, rank what fits them first, at
        `topic_emphasis` (per call: this service is shared). Raises
        seeds.SeedError for a seed with nothing to search for, and
        ValueError for an emphasis outside [0, 1] - both before any feed
        is read.

        `edition` (src/config/editions.py) chooses which signals are read
        (TrendService.signals_for: the uplifting ones are never the
        Devastating edition's, nor the bleak ones the positive's), the
        screen and the groups' topics.
        """

        started = now or datetime.now(timezone.utc)
        per_trend = max(1, min(per_trend, MAX_PER_TREND))

        ranking.weights(topic_emphasis)

        seeded = self.trends.seed(seed) if seed else None

        reads: list[SignalRead] = self.trends.read(signal_ids, edition) if signal_ids != [] else []

        signal_trends = [trend for read in reads for trend in read.trends]

        if search:
            self.trends.search_articles(signal_trends, per_trend)

        if seeded is not None:
            self.trends.search_articles([seeded], SEED_SEARCH)

        topics = topics_for(groups or None, edition)
        known = self.ingestion.stored_urls()

        rows: list[_Row] = []
        offered: list[_Offered] = []
        tallies: dict[str, _TrendTally] = {}
        row_of: dict[str, _Row] = {}

        sources = ([(SEED_SIGNAL, [seeded], None)] if seeded is not None else []) + [
            (read.signal.id, read.trends, read) for read in reads
        ]

        for source_id, trends, read in sources:

            row = _Row(
                source=source_id,
                name=read.signal.name if read else "Typed by a person",
                language=read.signal.language if read else None,
                method=f"trend:{read.signal.kind}" if read else "trend:seed",
                trends=len(trends),
                skipped=read.skipped if read else 0,
                error=read.error if read else None,
            )
            rows.append(row)
            row_of[source_id] = row

            fresh: list[str] = []
            published: dict[str, datetime] = {}

            for trend in trends:

                tally = tallies.setdefault(trend.id, _TrendTally())
                tally.stale = _too_old(trend.started_at, started, MAX_TREND_AGE)

                for article in trend.articles:

                    row.discovered += 1
                    tally.articles += 1

                    url = article.url

                    if not url.lower().startswith(("http://", "https://")) or not looks_like_article(url) or off_mission(url, edition):
                        row.not_articles += 1
                        continue

                    if tally.stale or _too_old(article.published or date_from_url(url), started, MAX_ARTICLE_AGE):
                        row.stale += 1
                        continue

                    key = comparable_url(url)

                    if key in known:
                        row.already_stored += 1
                        continue

                    # Also marks it for the rest of this round: the first
                    # trend to bring an article keeps it.
                    known.add(key)
                    fresh.append(url)

                    if article.published:
                        published[url] = article.published

                    title, title_from = _title_of(article)
                    offered.append(_Offered(trend=trend, article=article, title=title, title_from=title_from))

            # When we first knew of each article, for the freshness report,
            # as the topic rounds record theirs.
            self.ingestion.sightings.record(
                fresh,
                source_id=source_id,
                method=row.method,
                published=published,
                seen_at=started,
            )

        verdicts, readings, screen = self._screen(offered, edition)

        candidates: list[dict] = []
        to_rank: list[tuple[dict, Reading | None, str, float | None, str]] = []
        fits: dict[str, float] = {}
        nearest: dict[str, str] = {}
        screened: list[dict] = []
        kept_per_trend: dict[str, int] = defaultdict(int)
        values = virality([trend for _, trends, _ in sources for trend in trends])

        for item in offered:

            url = item.article.url
            row = row_of[item.trend.signal]
            tally = tallies[item.trend.id]

            if screen["status"] == "ok":
                row.judged += 1

            verdict = verdicts.get(url)

            if verdict is not None:
                row.screened += 1
                tally.screened += 1
                screened.append({
                    "url": url,
                    "source": row.source,
                    "sourceName": row.name,
                    "title": item.title,
                    "offMission": verdict.off_mission,
                    "margin": verdict.margin,
                    "nearestTopic": verdict.nearest_topic,
                    "trend": item.trend.name,
                })
                continue

            if kept_per_trend[item.trend.id] >= per_trend:
                row.deferred += 1
                continue

            kept_per_trend[item.trend.id] += 1
            row.candidates += 1
            tally.candidates += 1

            reading = readings.get(url)
            fit = ranking.group_fit(reading, topics) if groups else None

            if fit is not None:
                fits[url] = fit
                nearest[url] = reading.nearest_topic

            candidate = {
                "url": url,
                "source": domain_of(url),
                "sourceName": item.article.outlet or domain_of(url),
                "language": item.trend.language,
                "groups": [],
                "title": item.title,
                "titleFrom": item.title_from,
                "summary": item.article.snippet,
                "publishedAt": item.article.published.isoformat(timespec="seconds") if item.article.published else None,
                "method": row.method,
                "reading": (
                    {**reading.to_dict(), "groupFit": None if fit is None else round(fit, 4)}
                    if reading else None
                ),
                "trend": item.trend.card(),
            }

            candidates.append(candidate)
            to_rank.append((candidate, reading, row.source, fit, item.trend.id))

        applied = ranking.applied_emphasis(topic_emphasis, signal=bool(fits))

        standings = {
            row.source: ranking.Standing(reliability=0.0, judged=row.judged, kept=row.judged - row.screened)
            for row in rows
        }

        for candidate, reading, source_id, fit, trend in to_rank:
            candidate["rank"] = ranking.trend_rank(
                reading, standings[source_id], fit,
                virality=values.get(trend),
                emphasis=ranking.WITHOUT_TOPIC if applied is None else applied,
            )

        vectors = {
            url: reading.vector
            for url, reading in readings.items()
            if reading.vector is not None
        }

        candidates = ranking.ordered(candidates, fits, nearest, vectors)

        trends_out = []

        for _, trends, _ in sources:
            for trend in trends:
                tally = tallies[trend.id]
                trends_out.append({
                    **trend.card(),
                    "language": trend.language,
                    "virality": values.get(trend.id),
                    "articles": tally.articles,
                    "candidates": tally.candidates,
                    "screened": tally.screened,
                    "stale": tally.stale,
                    "notes": list(trend.notes),
                })

        return {
            "startedAt": started.isoformat(timespec="seconds"),
            "lens": LENS,
            "edition": edition,
            "groups": list(groups or []),
            "topics": topics if groups else [],
            "signals": [read.signal.id for read in reads],
            "seed": seed or None,
            "search": search,
            "perTrend": per_trend,
            # The topic rounds' key, so a page that reads it still can.
            "perSource": per_trend,
            "maxTrendAgeHours": int(MAX_TREND_AGE.total_seconds() // 3600),
            "sources": [row.to_dict() for row in rows],
            "trends": trends_out,
            "candidates": candidates,
            "ranking": ranking.described_trending(topic_emphasis, applied),
            "screen": screen,
            "screened": screened,
            "totals": {
                "sources": len(rows),
                "trends": sum(row.trends for row in rows),
                "discovered": sum(row.discovered for row in rows),
                "alreadyStored": sum(row.already_stored for row in rows),
                "notArticles": sum(row.not_articles for row in rows),
                "candidates": len(candidates),
                "deferred": sum(row.deferred for row in rows),
                "screened": sum(row.screened for row in rows),
                "stale": sum(row.stale for row in rows),
                "failed": sum(1 for row in rows if row.error and not row.trends),
                "sameStory": sum(1 for candidate in candidates if candidate.get("sameStoryAs")),
                "otherGroup": sum(1 for candidate in candidates if candidate.get("otherGroup")),
            },
        }

    def _screen(self, offered: list[_Offered], edition: str = "positive") -> tuple[dict, dict, dict]:
        """
        The mission screen over every offered article in one pass, as
        IngestionService._pick runs it: (verdicts, readings, state). With
        no screen, or inference/ unreachable, nothing is left out and the
        round says which.
        """

        screen = self.ingestion.screen_for(edition)
        state = {
            "status": "off" if screen is None else "ok",
            "margin": MARGIN,
            "margins": getattr(screen, "margins", MARGINS),
            "error": None,
        }

        if screen is None or not offered:
            return {}, {}, state

        try:
            assessments = screen.assess(
                [
                    Candidate(title=item.title, summary=item.article.snippet, language=item.trend.language)
                    for item in offered
                ],
                exempt=[False] * len(offered),
            )
        except Exception as exc:  # noqa: BLE001 - a screen that fails must not look like one that passed
            logger.warning("Mission screen unavailable for a trending round; nothing left out", exc_info=True)
            state.update(status="unavailable", error=str(exc))
            return {}, {}, state

        verdicts, readings = {}, {}

        for item, assessment in zip(offered, assessments):

            if assessment.verdict is not None:
                verdicts[item.article.url] = assessment.verdict

            if assessment.reading is not None:
                readings[item.article.url] = assessment.reading

        return verdicts, readings, state


def _title_of(article: TrendArticle) -> tuple[str, str]:
    """An article's title and where it came from: the signal's, the search's, or its link's."""

    if article.title:
        return article.title, "search" if article.found_by == "search" else "signal"

    return title_from_url(article.url) or article.url, "url"


def _too_old(moment: datetime | None, now: datetime, limit: timedelta) -> bool:
    """Older than `limit` at `now`; an undated thing is not too old (nothing says it is)."""

    if moment is None:
        return False

    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)

    return now - moment > limit
