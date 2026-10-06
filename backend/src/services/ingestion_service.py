"""
The ingestion path: configured sources -> discovered article URLs ->
analysis jobs.

Until this existed, the only way an article entered the system was a
person posting its URL to /analyze; the twelve source YAMLs, the RSS
strategy and DiscoveryService were never called by anything.

Each new URL becomes an ordinary analysis job on the same bounded queue
as a posted one - extracted, enriched, fact-checked and stored - so it
shows on /live, lands in the lake and is counted in the scraper stats
(purpose "ingestion"). That is the expensive part, and everything before
it exists to spend it only on articles worth it:

1. discovery is cheapest-first (the feed, then trafilatura's lenient
   discovery - see src/services/scraper/discovery.py);
2. discovery keeps only links that look like articles and match a
   configured topic, so off-topic pieces are never fetched just to be
   rejected by the admission filter, and only items from the last
   MAX_CANDIDATE_AGE when the feed dates them;
3. articles already in the lake are skipped - compared by host and path,
   so a tracking parameter does not make an old article new;
4. the mission screen leaves out what the publication never covers -
   elections, crime, accidents, celebrity (src/services/selection/
   mission_screen.py) - before the per-source cap, so a source's slots go
   to what is left;
5. at most `per_source` new articles per source per run.

Triggered by hand, never on a timer: every queued article costs a scrape,
an enrichment and an LLM call per claim. Two ways in:

- POST /ingest queues every new article found, up to `per_source`;
- a candidate round (`discover_candidates`, owned by
  src/services/selection/) only lists them, with the feed's title and
  summary, so a person or the AI selection can choose up to twenty before
  anything is fetched.

Both can be narrowed to up to three topic groups (src/config/topics.py
TOPIC_GROUPS): only the sources whose YAML names one of them are read, and
discovery is asked for those groups' topics alone - fewer feeds, fewer
section pages, and fewer off-topic articles scraped only to be rejected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import Callable
from urllib.parse import urlsplit

from src.config.topics import TOPIC_GROUPS, TOPICS
from src.models.core.source import NewsSource
from src.models.storage.lineage import DataLayer
from src.services.concurrency import bounded_map
from src.services.scraper.article_stats import comparable_url
from src.services.scraper.discovery import DiscoveryResult, DiscoveryService
from src.services.scraper.sightings import Sightings, sightings as default_sightings
from src.services.selection.mission_screen import MARGIN, MARGINS, Candidate, MissionScreen

logger = getLogger(__name__)

# Feeds are other people's servers and several are slow (two timed out in
# the 2026-09-23 check). A few at once keeps a run to seconds rather than
# the sum of every feed's latency, without hammering anyone.
DISCOVERY_CONCURRENCY = 4

# StartJob(url) -> (job_id, reused). The route's _start_job, with the
# purpose and thresholds already bound.
StartJob = Callable[[str], tuple[str, bool]]

# At most this many topic groups per run: more is close to "everything",
# which is what the narrowing exists to avoid.
MAX_GROUPS = 3

# Older items are not offered: this is news. On 2026-10-06 the feeds of a
# Culture, Society and Health round carried 38 items older than this -
# WHO's back to 2025, RTVE's from June 2022 - and 54 older than 14 days,
# 9 of them MIT News research stories still worth reading.
MAX_CANDIDATE_AGE = timedelta(days=30)

# The mission screen reads this many of a source's new articles per one
# wanted from it, in feed order, and the source's slots are filled from
# what passes. Screening all of El País's 159 to keep two would embed the
# whole feed for nothing.
SCREEN_DEPTH = 5


def topics_for(groups: list[str] | None) -> list[str]:
    """The topic keys of `groups`, in TOPICS order; every topic when no group is given."""

    if not groups:
        return list(TOPICS)

    wanted = {topic for group in groups for topic in TOPIC_GROUPS[group]}

    return [topic for topic in TOPICS if topic in wanted]


def title_from_url(url: str) -> str | None:
    """
    A readable stand-in title from the URL's slug, for a link whose feed
    gave none (section pages give only links): ".../rewilding-the-ebro-
    delta.html" -> "Rewilding the ebro delta". None for a slug too short
    to say anything. The segment before the last when the last is only an
    id: RTVE's ".../asi-se-hace-autentico-bacalao/17174859.shtml" came
    back untitled - and so unjudged by the mission screen - on 2026-10-06.
    """

    segments = [segment for segment in urlsplit(url).path.split("/") if segment]

    for segment in reversed(segments[-2:]):

        slug = re.sub(r"\.s?html?$", "", segment)
        words = [word for word in re.split(r"[-_]+", slug) if word and not word.isdigit()]

        if len(words) >= 3:
            text = " ".join(words)
            return text[0].upper() + text[1:]

    return None


def _title(url: str, result: DiscoveryResult) -> str | None:
    """A candidate's title: its feed's, or one made from its slug."""

    return (result.details.get(url) or {}).get("title") or title_from_url(url)


@dataclass
class SourceRun:

    source: str

    name: str

    method: str | None = None

    discovered: int = 0

    already_stored: int = 0

    queued: list[dict] = field(default_factory=list)

    # New articles found beyond per_source, left for a later run.
    deferred: int = 0

    # Left out by the mission screen, and dropped as older than
    # MAX_CANDIDATE_AGE.
    screened: int = 0

    stale: int = 0

    error: str | None = None

    def to_dict(self) -> dict:

        return {
            "source": self.source,
            "name": self.name,
            "method": self.method,
            "discovered": self.discovered,
            "alreadyStored": self.already_stored,
            "queued": self.queued,
            "deferred": self.deferred,
            "screened": self.screened,
            "stale": self.stale,
            "error": self.error,
        }


@dataclass
class _Picked:
    """One source's share of a run, after the screen and the cap."""

    # At most per_source, in feed order.
    urls: list[str]

    # Left out by the mission screen, with why.
    screened: list[dict]

    # New, and neither picked nor left out: for a later run.
    deferred: int


class IngestionService:

    def __init__(
        self,
        sources: list[NewsSource],
        lake,
        discovery: DiscoveryService | None = None,
        sightings: Sightings | None = None,
        screen: MissionScreen | None = None,
    ):
        self.sources = sources
        self.lake = lake
        self.discovery = discovery or DiscoveryService(max_age=MAX_CANDIDATE_AGE)
        self.sightings = sightings if sightings is not None else default_sightings

        # None: nothing is screened (the tests' default); the app passes one.
        self.screen = screen

        self.last_run: dict | None = None

    def enabled_sources(self) -> list[NewsSource]:

        return sorted(
            (source for source in self.sources if source.enabled),
            key=lambda source: source.id,
        )

    def sources_for(
        self,
        groups: list[str] | None = None,
        source_ids: list[str] | None = None,
    ) -> list[NewsSource]:
        """The enabled sources covering any of `groups`, further limited to `source_ids` when given."""

        return [
            source
            for source in self.enabled_sources()
            if (not groups or set(source.groups) & set(groups))
            and (source_ids is None or source.id in source_ids)
        ]

    def run(
        self,
        start_job: StartJob,
        source_ids: list[str] | None = None,
        per_source: int = 3,
        groups: list[str] | None = None,
    ) -> dict:

        started = datetime.now(timezone.utc)

        sources = self.sources_for(groups, source_ids)
        topics = topics_for(groups)

        known = self._stored_urls()

        # Discovery in parallel (network-bound, other people's servers);
        # queueing in order afterwards, on this thread, so the jobs are
        # submitted in a stable order and the known-set is not shared.
        discovered = bounded_map(
            lambda source: self._discover(source, topics),
            sources,
            max_workers=DISCOVERY_CONCURRENCY,
            thread_name_prefix="discovery",
        )

        runs = []
        fresh_by_source = []

        for source, result in zip(sources, discovered):

            run = SourceRun(source=source.id, name=source.name)
            runs.append(run)

            run.method = result.method
            run.discovered = len(result.urls)
            run.stale = result.stale
            run.error = result.error if not result.urls else None

            fresh = []
            fresh_by_source.append(fresh)

            for url in result.urls:

                key = comparable_url(url)

                if key in known:
                    run.already_stored += 1
                    continue

                # Also marks it for the rest of this run: two sources
                # syndicating one article queue it once.
                known.add(key)
                fresh.append(url)

            # When we first knew of each new article, and when its feed
            # says it was published - deferred ones included: the wait
            # until a later run queues them is part of their delay.
            # src/services/freshness.py.
            self.sightings.record(
                fresh,
                source_id=source.id,
                method=result.method,
                published=result.published,
                seen_at=started,
            )

        picked, screen = self._pick(sources, discovered, fresh_by_source, per_source)

        for run, choice in zip(runs, picked):

            for url in choice.urls:

                try:
                    job_id, reused = start_job(url)
                    run.queued.append({"url": url, "jobId": job_id, "reused": reused})
                except Exception as exc:
                    logger.warning("Could not queue %s: %s", url, exc)
                    run.error = f"could not queue {url}: {exc}"

            run.deferred = choice.deferred
            run.screened = len(choice.screened)

        report = {
            "startedAt": started.isoformat(timespec="seconds"),
            "perSource": per_source,
            "groups": list(groups or []),
            "screen": screen,
            "screened": [entry for choice in picked for entry in choice.screened],
            "totals": {
                "sources": len(runs),
                "discovered": sum(run.discovered for run in runs),
                "alreadyStored": sum(run.already_stored for run in runs),
                "queued": sum(len(run.queued) for run in runs),
                "deferred": sum(run.deferred for run in runs),
                "screened": sum(run.screened for run in runs),
                "stale": sum(run.stale for run in runs),
                "failed": sum(1 for run in runs if run.error and not run.discovered),
            },
            "sources": [run.to_dict() for run in runs],
        }

        self.last_run = report

        return report

    def discover_candidates(
        self,
        groups: list[str] | None = None,
        source_ids: list[str] | None = None,
        per_source: int = 3,
    ) -> dict:
        """
        Discovery without queueing: up to `per_source` new articles from
        each source covering `groups`, each with what its feed says about
        it (title, summary, time), for someone to choose from. Nothing is
        fetched beyond the feeds and section pages, and nothing is
        analysed - src/services/selection/ owns what happens next.
        """

        started = datetime.now(timezone.utc)

        sources = self.sources_for(groups, source_ids)
        topics = topics_for(groups)

        known = self._stored_urls()

        discovered = bounded_map(
            lambda source: self._discover(source, topics),
            sources,
            max_workers=DISCOVERY_CONCURRENCY,
            thread_name_prefix="discovery",
        )

        rows = []
        candidates = []
        fresh_by_source = []
        already_by_source = []

        for source, result in zip(sources, discovered):

            fresh = []
            already = 0

            for url in result.urls:

                key = comparable_url(url)

                if key in known:
                    already += 1
                    continue

                known.add(key)
                fresh.append(url)

            fresh_by_source.append(fresh)
            already_by_source.append(already)

            # The record ingestion keeps of when an article was first
            # seen, for the freshness report: a candidate nobody picks
            # was still seen.
            self.sightings.record(
                fresh,
                source_id=source.id,
                method=result.method,
                published=result.published,
                seen_at=started,
            )

        picked, screen = self._pick(sources, discovered, fresh_by_source, per_source)

        for source, result, already, choice in zip(sources, discovered, already_by_source, picked):

            for url in choice.urls:

                details = result.details.get(url) or {}
                published = result.published.get(url)
                feed_title = details.get("title")

                candidates.append({
                    "url": url,
                    "source": source.id,
                    "sourceName": source.name,
                    "language": source.language,
                    "groups": [group for group in source.groups if not groups or group in groups],
                    "title": feed_title or title_from_url(url),
                    "titleFrom": "feed" if feed_title else "url",
                    "summary": details.get("summary"),
                    "publishedAt": published.isoformat(timespec="seconds") if published else None,
                    "method": result.method,
                })

            rows.append({
                "source": source.id,
                "name": source.name,
                "language": source.language,
                "method": result.method,
                "discovered": len(result.urls),
                "alreadyStored": already,
                "candidates": len(choice.urls),
                "deferred": choice.deferred,
                "screened": len(choice.screened),
                "stale": result.stale,
                "error": result.error if not result.urls else None,
            })

        return {
            "startedAt": started.isoformat(timespec="seconds"),
            "groups": list(groups or []),
            "topics": topics,
            "perSource": per_source,
            "sources": rows,
            "candidates": candidates,
            "screen": screen,
            "screened": [entry for choice in picked for entry in choice.screened],
            "totals": {
                "sources": len(rows),
                "discovered": sum(row["discovered"] for row in rows),
                "alreadyStored": sum(row["alreadyStored"] for row in rows),
                "candidates": len(candidates),
                "deferred": sum(row["deferred"] for row in rows),
                "screened": sum(row["screened"] for row in rows),
                "stale": sum(row["stale"] for row in rows),
                "failed": sum(1 for row in rows if row["error"] and not row["discovered"]),
            },
        }

    def _pick(
        self,
        sources: list[NewsSource],
        results: list[DiscoveryResult],
        fresh_by_source: list[list[str]],
        per_source: int,
    ) -> tuple[list[_Picked], dict]:
        """
        Each source's share: the mission screen over the first
        per_source x SCREEN_DEPTH of its new articles, then the first
        per_source of those it kept. One batched pass over every source's
        share, not one per source. The screen's state comes back with it
        - "ok", "off" (none configured) or "unavailable" (inference/ could
        not be reached: nothing was left out, and the round says so).
        """

        screening = [
            self.screen is not None and not source.positive_editorial
            for source in sources
        ]

        pools = [
            fresh[: per_source * SCREEN_DEPTH] if screened else []
            for fresh, screened in zip(fresh_by_source, screening)
        ]

        titled = [
            (url, Candidate(
                title=_title(url, result),
                summary=(result.details.get(url) or {}).get("summary"),
                language=source.language,
            ))
            for source, pool, result in zip(sources, pools, results)
            for url in pool
        ]

        state = {"status": "off" if self.screen is None else "ok", "margin": MARGIN, "margins": MARGINS, "error": None}
        verdicts = {}

        if titled:
            try:
                for (url, _), verdict in zip(titled, self.screen.screen([candidate for _, candidate in titled])):
                    if verdict is not None:
                        verdicts[url] = verdict
            except Exception as exc:
                # Every candidate is kept and the round says why: a screen
                # that fails must not look like one that passed everything.
                logger.warning("Mission screen unavailable; nothing left out", exc_info=True)
                state.update(status="unavailable", error=str(exc))
                pools = [[] for _ in pools]
                verdicts = {}

        picked = []

        for source, result, fresh, pool in zip(sources, results, fresh_by_source, pools):

            if not pool:
                urls = fresh[:per_source]
                out = []
            else:
                urls = [url for url in pool if url not in verdicts][:per_source]
                out = [url for url in pool if url in verdicts]

            picked.append(_Picked(
                urls=urls,
                screened=[
                    {
                        "url": url,
                        "source": source.id,
                        "sourceName": source.name,
                        "title": _title(url, result),
                        "offMission": verdicts[url].off_mission,
                        "margin": verdicts[url].margin,
                        "nearestTopic": verdicts[url].nearest_topic,
                    }
                    for url in out
                ],
                deferred=len(fresh) - len(urls) - len(out),
            ))

        return picked, state

    def _discover(self, source: NewsSource, topics: list[str] | None = None) -> DiscoveryResult:

        try:
            return self.discovery.run(source, topics=topics if topics is not None else list(TOPICS))
        except Exception as exc:
            logger.warning("Discovery failed for %s", source.id, exc_info=True)
            return DiscoveryResult(error=str(exc))

    def _stored_urls(self) -> set[str]:
        """Every article URL already in the lake's raw layer."""

        try:
            records = self.lake.list(DataLayer.RAW)
        except Exception:
            logger.warning("Could not read the lake; nothing counts as stored", exc_info=True)
            return set()

        urls = set()

        for record in records:

            url = (record.get("lineage") or {}).get("source_url") or (
                record.get("article") or {}
            ).get("url")

            if url:
                urls.add(comparable_url(url))

        return urls
