"""
Is each configured source up, and can we actually get articles out of it?

The scraper stats (request_stats.py) answer that only for pages someone
happened to ask for; a source nobody ingested lately looks exactly like
a healthy one. The probe asks on purpose, for every enabled source:

1. **Feed** - the configured RSS feed, then trafilatura's lenient feed
   discovery: exactly what ingestion does first.
2. **Topic pages** - the source's topic section pages
   (strategies/topic_pages.py), always, even when the feed works: how
   many article links they add beyond the feed is the point of asking.
3. **Sample** - up to `per_source` of the links found, split between
   feed and topic pages, each extracted through the real cascade with
   purpose `probe`. A feed full of links nobody can read is not "up".

and calls it:

- `up`: links from the feed, and at least half the sample extracted;
- `degraded`: articles can be had, but not the normal way - the feed is
  dead and only the topic pages produce links, or fewer than half the
  sample extracted;
- `down`: nothing extracted - no links anywhere, or every sampled
  article failed.

Plus one check that is not about a source: a real query to SearXNG in
each language, reporting which upstream engines answered. Every fact
check's evidence comes through it, and on 2026-09-25 it was returning
nothing for 68 of 69 queries with no sign of it anywhere.

Triggered by hand (POST /scraper/probe), never on a timer: a run sends
~10-15 requests to every source. The last report is kept on disk, so the
/scraper page still has it after a restart.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from logging import getLogger
from pathlib import Path

from src.config.topics import TOPICS
from src.models.core.source import NewsSource
from src.services.concurrency import bounded_map
from src.services.scraper.discovery import DiscoveryService
from src.services.scraper.extractor import ExtractorService
from src.services.scraper.request_stats import Outcome, Purpose, RequestStats, request_stats
from src.services.scraper.strategies.rss import RSSDiscoveryStrategy
from src.services.scraper.strategies.topic_pages import TopicPageDiscoveryStrategy
from src.services.scraper.strategies.trafilatura_feeds import TrafilaturaFeedDiscoveryStrategy

logger = getLogger(__name__)

# Sources probed at once. Each source's own requests stay sequential -
# one host is never asked twice at the same time - so this bounds how
# many *different* sites are being read, like ingestion's
# DISCOVERY_CONCURRENCY.
PROBE_CONCURRENCY = 4

# Below this share of the sample extracting, a source is degraded.
HEALTHY_EXTRACTION_RATE = 0.5

# One everyday query per language the sources publish in: if these come
# back empty, no claim's will come back with anything.
SEARCH_CHECKS = (("renewable energy", "en"), ("energía renovable", "es"))


class _Recorder(RequestStats):
    """
    Keeps what each sampled URL came to, and still counts it in the
    shared stats: the probe needs the reason per URL, /scraper needs the
    probe's requests counted like every other.
    """

    def __init__(self, inner: RequestStats):

        super().__init__()

        self.inner = inner
        self.by_url: dict[str, dict] = {}
        self._urls_lock = threading.Lock()

    def record(self, url, outcome, purpose=Purpose.ARTICLE, strategy="", source_id=None,
               status=None, error=None, elapsed_ms=0.0, sent=1, tried=None) -> None:

        with self._urls_lock:
            self.by_url[url] = {
                "outcome": Outcome(outcome).value,
                "status": status,
                "error": error,
                "strategy": strategy or None,
                "ms": round(elapsed_ms),
            }

        self.inner.record(
            url, outcome, purpose=purpose, strategy=strategy, source_id=source_id,
            status=status, error=error, elapsed_ms=elapsed_ms, sent=sent, tried=tried,
        )


@dataclass
class SourceProbeResult:

    source: str

    name: str

    language: str

    status: str = "down"

    reason: str = ""

    homepage_status: int | None = None

    homepage_error: str | None = None

    feed_method: str | None = None

    feed_links: int = 0

    feed_error: str | None = None

    topic_links: int = 0

    # Topic-page links the feed did not already have.
    extra_links: int = 0

    sections: list[dict] = field(default_factory=list)

    sample: list[dict] = field(default_factory=list)

    elapsed_ms: int = 0

    @property
    def extracted(self) -> int:

        return sum(1 for item in self.sample if item["ok"])

    def to_dict(self) -> dict:

        return {
            "source": self.source,
            "name": self.name,
            "language": self.language,
            "status": self.status,
            "reason": self.reason,
            "homepageStatus": self.homepage_status,
            "homepageError": self.homepage_error,
            "feedMethod": self.feed_method,
            "feedLinks": self.feed_links,
            "feedError": self.feed_error,
            "topicLinks": self.topic_links,
            "extraLinks": self.extra_links,
            "sections": self.sections,
            "sampled": len(self.sample),
            "extracted": self.extracted,
            "sample": self.sample,
            "elapsedMs": self.elapsed_ms,
        }


def classify_source(result: SourceProbeResult) -> tuple[str, str]:
    """(status, reason) for one probed source. Pure, so it is tested alone."""

    sampled = len(result.sample)
    extracted = result.extracted

    if not result.feed_links and not result.topic_links:
        if result.homepage_error:
            return "down", f"site unreachable ({result.homepage_error}) and no feed"
        return "down", "no article links in the feed or on any topic page"

    if sampled and not extracted:
        reasons = sorted({item["outcome"] for item in result.sample})
        return "down", f"links found, but none of {sampled} sampled articles extracted ({', '.join(reasons)})"

    rate = extracted / sampled if sampled else 0.0

    if not result.feed_links:
        return "degraded", (
            f"feed gives nothing ({result.feed_error or 'no links'}); "
            f"{result.topic_links} links from topic pages, {extracted}/{sampled} extracted"
        )

    if rate < HEALTHY_EXTRACTION_RATE:
        return "degraded", f"only {extracted}/{sampled} sampled articles extracted"

    return "up", f"{result.feed_links} feed links, {extracted}/{sampled} extracted"


class SourceProbe:

    def __init__(
        self,
        sources: list[NewsSource],
        stats: RequestStats | None = None,
        path: Path | None = None,
        feed_discovery: DiscoveryService | None = None,
        topic_pages: TopicPageDiscoveryStrategy | None = None,
        extractor_factory=None,
        search_client=None,
    ):
        self.sources = sources
        self.stats = stats if stats is not None else request_stats
        self.path = Path(path) if path is not None else None

        # Only the two feed steps: topic pages are probed separately and
        # always, to measure what they add.
        self.feed_discovery = feed_discovery or DiscoveryService(
            [RSSDiscoveryStrategy(), TrafilaturaFeedDiscoveryStrategy()],
            stats=self.stats,
        )
        self.topic_pages = topic_pages or TopicPageDiscoveryStrategy()

        # None skips the search check (tests; a probe of the sources only).
        self.search_client = search_client

        self._extractor_factory = extractor_factory or (
            lambda stats: ExtractorService(stats=stats, sources=self.sources)
        )

        self._lock = threading.Lock()
        self._running = False
        self._started_at: str | None = None
        self._error: str | None = None
        self.last_report: dict | None = self._load()

    # ------------------------------------------------------------------

    def enabled_sources(self) -> list[NewsSource]:

        return sorted(
            (source for source in self.sources if source.enabled),
            key=lambda source: source.id,
        )

    def state(self) -> dict:

        with self._lock:
            return {
                "running": self._running,
                "startedAt": self._started_at,
                "error": self._error,
                "report": self.last_report,
            }

    def start(self, source_ids: list[str] | None = None, per_source: int = 5) -> bool:
        """
        Runs the probe on a background thread. False when one is already
        running: two at once would only double the load on every source.
        """

        with self._lock:

            if self._running:
                return False

            self._running = True
            self._started_at = _now()
            self._error = None

        threading.Thread(
            target=self._run_in_background,
            args=(source_ids, per_source),
            name="source-probe",
            daemon=True,
        ).start()

        return True

    def _run_in_background(self, source_ids, per_source) -> None:

        try:
            self.run(source_ids, per_source)
        except Exception as exc:
            logger.exception("Source probe failed")
            with self._lock:
                self._error = str(exc)
        finally:
            with self._lock:
                self._running = False

    def run(self, source_ids: list[str] | None = None, per_source: int = 5) -> dict:

        started = datetime.now(timezone.utc)

        sources = [
            source
            for source in self.enabled_sources()
            if source_ids is None or source.id in source_ids
        ]

        results = bounded_map(
            lambda source: self.probe(source, per_source),
            sources,
            max_workers=PROBE_CONCURRENCY,
            thread_name_prefix="source-probe",
        )

        search = self._search_health()

        counts = {status: 0 for status in ("up", "degraded", "down")}

        for result in results:
            counts[result.status] += 1

        report = {
            "startedAt": started.isoformat(),
            "finishedAt": datetime.now(timezone.utc).isoformat(),
            "perSource": per_source,
            "totals": {
                "sources": len(results),
                **counts,
                "feedLinks": sum(r.feed_links for r in results),
                "topicLinks": sum(r.topic_links for r in results),
                "extraLinks": sum(r.extra_links for r in results),
                "sampled": sum(len(r.sample) for r in results),
                "extracted": sum(r.extracted for r in results),
            },
            "sources": [result.to_dict() for result in results],
            "search": search,
        }

        with self._lock:
            self.last_report = report

        self._save(report)

        return report

    def _search_health(self) -> list[dict]:

        if self.search_client is None:
            return []

        checks = []

        for query, language in SEARCH_CHECKS:
            try:
                checks.append({"language": language, **self.search_client.health(query, language)})
            except Exception as exc:
                checks.append({"language": language, "query": query, "ok": False, "error": str(exc)})

        return checks

    def probe(self, source: NewsSource, per_source: int = 5) -> SourceProbeResult:

        started = time.perf_counter()

        result = SourceProbeResult(
            source=source.id,
            name=source.name,
            language=source.language or "en",
        )

        try:
            feed = self.feed_discovery.run(source, topics=list(TOPICS))
            feed_urls = feed.urls
            result.feed_method = feed.method
            result.feed_error = feed.error
        except Exception as exc:
            feed_urls = []
            result.feed_error = str(exc)

        result.feed_links = len(feed_urls)

        try:
            crawl = self.topic_pages.crawl(source, list(TOPICS))
            topic_urls = crawl.urls
            result.homepage_status = crawl.homepage_status
            result.homepage_error = crawl.homepage_error
            result.sections = [section.to_dict() for section in crawl.sections]
        except Exception as exc:
            topic_urls = []
            result.homepage_error = str(exc)

        known = set(feed_urls)
        extra = [url for url in topic_urls if url not in known]

        result.topic_links = len(topic_urls)
        result.extra_links = len(extra)

        result.sample = self._sample(source, _interleave(feed_urls, extra)[:max(per_source, 0)], feed_urls)

        result.status, result.reason = classify_source(result)
        result.elapsed_ms = round((time.perf_counter() - started) * 1000)

        return result

    def _sample(self, source: NewsSource, urls: list[str], feed_urls: list[str]) -> list[dict]:

        recorder = _Recorder(self.stats)
        extractor = self._extractor_factory(recorder)
        from_feed = set(feed_urls)

        sample = []

        for url in urls:

            try:
                news = extractor.extract(source, url, purpose=Purpose.PROBE)
            except Exception as exc:
                news = None
                recorder.by_url.setdefault(url, {"outcome": Outcome.ERROR.value, "error": str(exc)})

            seen = recorder.by_url.get(url, {})

            sample.append({
                "url": url,
                "via": "feed" if url in from_feed else "topic_page",
                "ok": news is not None,
                "outcome": seen.get("outcome", Outcome.OK.value if news else Outcome.ERROR.value),
                "status": seen.get("status"),
                "error": seen.get("error"),
                "strategy": seen.get("strategy"),
                "ms": seen.get("ms"),
                "title": bool(news and news.title),
                "author": bool(news and news.author),
                "date": bool(news and news.published_at),
                "chars": len(news.content) if news else 0,
            })

        return sample

    # ------------------------------------------------------------------

    def _load(self) -> dict | None:

        if self.path is None or not self.path.exists():
            return None

        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Could not read the last probe report from %s", self.path, exc_info=True)
            return None

    def _save(self, report: dict) -> None:
        """Fail-soft, like the scraper stats: a full disk must not lose the answer."""

        if self.path is None:
            return

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_name(f"{self.path.name}.tmp")
            temporary.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(temporary, self.path)
        except Exception:
            logger.warning("Could not save the probe report to %s", self.path, exc_info=True)


def _interleave(first: list[str], second: list[str]) -> list[str]:
    """a1, b1, a2, b2... so a short sample still tests both kinds of link."""

    out = []

    for index in range(max(len(first), len(second))):
        if index < len(first):
            out.append(first[index])
        if index < len(second):
            out.append(second[index])

    return out


def _now() -> str:

    return datetime.now(timezone.utc).isoformat()
