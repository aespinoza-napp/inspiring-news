"""
A health check for the configured sources: for every source YAML, does
discovery find article links, and does the extraction cascade turn a
couple of them into an article with a title, an author and a date?

Nothing is stored and nothing is analysed. This answers "is every page
we have configured still working?" - the question ingestion cannot,
because ingestion skips what is already in the lake and hands the rest to
a full analysis, so a source whose articles stopped extracting looks the
same as one with nothing new.

Every source is checked, disabled ones included: a disabled source is
the one most likely to have been switched off for a reason that may no
longer hold.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from logging import getLogger
from threading import Lock

from src.config.topics import TOPICS
from src.models.core.source import NewsSource
from src.services.concurrency import bounded_map
from src.services.scraper.discovery import DiscoveryResult, DiscoveryService
from src.services.scraper.extractor import ExtractorService
from src.services.scraper.request_stats import Outcome, Purpose, RequestStats, request_stats

logger = getLogger(__name__)

# The same ceiling ingestion's discovery uses, for the same reason: other
# people's servers, several of them slow. Each source's own articles are
# then fetched one after another, so no single site gets more than one
# request at a time from a check.
CHECK_CONCURRENCY = 4

# What a source needs to be reported as working, per sample article.
# The body is already enforced by the extractor's own validator; these
# are what the lake and the fact checker lean on beyond the body.
METADATA_CHECKED = ("title", "author", "published_at")


class _Recorder:
    """
    Stands between the extractor and the process-wide stats. `extract()`
    answers only "article or None"; the check has to say *why* None - a
    403, a timeout, a page too short - so each record is kept here by URL
    and forwarded unchanged, so a check's fetches still show on /scraper
    like every other.
    """

    def __init__(self, forward: RequestStats):
        self.forward = forward
        self.by_url: dict[str, dict] = {}
        self._lock = Lock()

    def record(self, url: str, outcome: Outcome, **details) -> None:

        with self._lock:
            self.by_url[url] = {"outcome": Outcome(outcome).value, **details}

        self.forward.record(url, outcome, **details)


@dataclass
class SampleCheck:

    url: str

    outcome: str = Outcome.ERROR.value

    strategy: str | None = None

    tried: list[str] = field(default_factory=list)

    status: int | None = None

    error: str | None = None

    elapsed_ms: int = 0

    title: str | None = None

    author: str | None = None

    published_at: str | None = None

    body_length: int = 0

    language: str | None = None

    def missing(self) -> list[str]:

        if self.outcome != Outcome.OK.value:
            return []

        return [name for name in METADATA_CHECKED if not getattr(self, name)]

    def to_dict(self) -> dict:

        return {
            "url": self.url,
            "outcome": self.outcome,
            "strategy": self.strategy,
            "tried": self.tried,
            "status": self.status,
            "error": self.error,
            "elapsedMs": self.elapsed_ms,
            "title": self.title,
            "author": self.author,
            "publishedAt": self.published_at,
            "bodyLength": self.body_length,
            "language": self.language,
            "missing": self.missing(),
        }


@dataclass
class SourceCheck:

    source: NewsSource

    discovery: DiscoveryResult = field(default_factory=DiscoveryResult)

    samples: list[SampleCheck] = field(default_factory=list)

    elapsed_ms: int = 0

    def verdict(self) -> str:
        """
        - `broken`: nothing to extract, or not one sample extracted.
        - `partial`: some extracted, or all extracted but missing a title,
          author or date.
        - `ok`: every sample extracted with all three.
        """

        if not self.discovery.urls or not self.samples:
            return "broken"

        extracted = [sample for sample in self.samples if sample.outcome == Outcome.OK.value]

        if not extracted:
            return "broken"

        if len(extracted) < len(self.samples) or any(sample.missing() for sample in extracted):
            return "partial"

        return "ok"

    def to_dict(self) -> dict:

        source = self.source

        return {
            "source": source.id,
            "name": source.name,
            "language": source.language,
            "enabled": source.enabled,
            "requiresJavascript": source.requires_javascript,
            "baseUrl": str(source.base_url),
            "rssUrl": str(source.rss_url) if source.rss_url else None,
            "verdict": self.verdict(),
            "discovery": {
                "method": self.discovery.method,
                "tried": self.discovery.tried,
                "found": len(self.discovery.urls),
                "error": self.discovery.error if not self.discovery.urls else None,
            },
            "samples": [sample.to_dict() for sample in self.samples],
            "elapsedMs": self.elapsed_ms,
        }


class SourceCheckService:

    def __init__(
        self,
        sources: list[NewsSource],
        discovery: DiscoveryService | None = None,
        extractor: ExtractorService | None = None,
        stats: RequestStats | None = None,
    ):
        self.sources = sources
        self.discovery = discovery or DiscoveryService()

        self.recorder = _Recorder(stats if stats is not None else request_stats)

        # Its own extractor, so every record it makes passes through the
        # recorder. The sources are handed over too: a disabled source is
        # checked as itself, and the extractor must not go and re-read
        # the YAMLs to resolve it.
        self.extractor = extractor or ExtractorService(stats=self.recorder, sources=sources)

        self.last_run: dict | None = None

    def all_sources(self) -> list[NewsSource]:

        return sorted(self.sources, key=lambda source: source.id)

    def run(self, source_ids: list[str] | None = None, per_source: int = 2) -> dict:

        started = datetime.now(timezone.utc)

        sources = [
            source
            for source in self.all_sources()
            if source_ids is None or source.id in source_ids
        ]

        checks = bounded_map(
            lambda source: self._check(source, per_source),
            sources,
            max_workers=CHECK_CONCURRENCY,
            thread_name_prefix="source-check",
        )

        verdicts = [check.verdict() for check in checks]

        report = {
            "startedAt": started.isoformat(timespec="seconds"),
            "perSource": per_source,
            "totals": {
                "sources": len(checks),
                "ok": verdicts.count("ok"),
                "partial": verdicts.count("partial"),
                "broken": verdicts.count("broken"),
            },
            "sources": [check.to_dict() for check in checks],
        }

        self.last_run = report

        return report

    def _check(self, source: NewsSource, per_source: int) -> SourceCheck:

        started = time.perf_counter()

        check = SourceCheck(source=source)

        try:
            check.discovery = self.discovery.run(source, topics=list(TOPICS))
        except Exception as exc:
            logger.warning("Discovery failed for %s", source.id, exc_info=True)
            check.discovery = DiscoveryResult(error=str(exc))

        # One after another: this is one site, and a check should not be
        # what makes it start refusing us.
        for url in check.discovery.urls[:per_source]:
            check.samples.append(self._sample(source, url))

        check.elapsed_ms = round((time.perf_counter() - started) * 1000)

        return check

    def _sample(self, source: NewsSource, url: str) -> SampleCheck:

        sample = SampleCheck(url=url)

        try:
            news = self.extractor.extract(source, url, purpose=Purpose.SOURCE_CHECK)
        except Exception as exc:
            logger.warning("Extraction raised for %s", url, exc_info=True)
            sample.error = str(exc)
            return sample

        recorded = self.recorder.by_url.get(url, {})

        sample.outcome = recorded.get("outcome", Outcome.OK.value if news else Outcome.ERROR.value)
        sample.strategy = recorded.get("strategy") or None
        sample.tried = recorded.get("tried") or []
        sample.status = recorded.get("status")
        sample.error = recorded.get("error")
        sample.elapsed_ms = round(recorded.get("elapsed_ms") or 0)

        if news is not None:
            sample.title = news.title
            sample.author = news.author
            sample.published_at = news.published_at.isoformat() if news.published_at else None
            sample.body_length = len(news.content or "")
            sample.language = news.language

        return sample
