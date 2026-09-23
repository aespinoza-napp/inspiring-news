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
   rejected by the admission filter;
3. articles already in the lake are skipped - compared by host and path,
   so a tracking parameter does not make an old article new;
4. at most `per_source` new articles per source per run.

Triggered by hand (POST /ingest), never on a timer: every queued article
costs a scrape, an enrichment and an LLM call per claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from logging import getLogger
from typing import Callable

from src.config.topics import TOPICS
from src.models.core.source import NewsSource
from src.models.storage.lineage import DataLayer
from src.services.concurrency import bounded_map
from src.services.scraper.article_stats import comparable_url
from src.services.scraper.discovery import DiscoveryResult, DiscoveryService

logger = getLogger(__name__)

# Feeds are other people's servers and several are slow (two timed out in
# the 2026-09-23 check). A few at once keeps a run to seconds rather than
# the sum of every feed's latency, without hammering anyone.
DISCOVERY_CONCURRENCY = 4

# StartJob(url) -> (job_id, reused). The route's _start_job, with the
# purpose and thresholds already bound.
StartJob = Callable[[str], tuple[str, bool]]


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
            "error": self.error,
        }


class IngestionService:

    def __init__(
        self,
        sources: list[NewsSource],
        lake,
        discovery: DiscoveryService | None = None,
    ):
        self.sources = sources
        self.lake = lake
        self.discovery = discovery or DiscoveryService()
        self.last_run: dict | None = None

    def enabled_sources(self) -> list[NewsSource]:

        return sorted(
            (source for source in self.sources if source.enabled),
            key=lambda source: source.id,
        )

    def run(
        self,
        start_job: StartJob,
        source_ids: list[str] | None = None,
        per_source: int = 3,
    ) -> dict:

        started = datetime.now(timezone.utc)

        sources = [
            source
            for source in self.enabled_sources()
            if source_ids is None or source.id in source_ids
        ]

        known = self._stored_urls()

        # Discovery in parallel (network-bound, other people's servers);
        # queueing in order afterwards, on this thread, so the jobs are
        # submitted in a stable order and the known-set is not shared.
        discovered = bounded_map(
            self._discover,
            sources,
            max_workers=DISCOVERY_CONCURRENCY,
            thread_name_prefix="discovery",
        )

        runs = []

        for source, result in zip(sources, discovered):

            run = SourceRun(source=source.id, name=source.name)
            runs.append(run)

            run.method = result.method
            run.discovered = len(result.urls)
            run.error = result.error if not result.urls else None

            fresh = []

            for url in result.urls:

                key = comparable_url(url)

                if key in known:
                    run.already_stored += 1
                    continue

                # Also marks it for the rest of this run: two sources
                # syndicating one article queue it once.
                known.add(key)
                fresh.append(url)

            for url in fresh[:per_source]:

                try:
                    job_id, reused = start_job(url)
                    run.queued.append({"url": url, "jobId": job_id, "reused": reused})
                except Exception as exc:
                    logger.warning("Could not queue %s: %s", url, exc)
                    run.error = f"could not queue {url}: {exc}"

            run.deferred = max(len(fresh) - per_source, 0)

        report = {
            "startedAt": started.isoformat(timespec="seconds"),
            "perSource": per_source,
            "totals": {
                "sources": len(runs),
                "discovered": sum(run.discovered for run in runs),
                "alreadyStored": sum(run.already_stored for run in runs),
                "queued": sum(len(run.queued) for run in runs),
                "deferred": sum(run.deferred for run in runs),
                "failed": sum(1 for run in runs if run.error and not run.discovered),
            },
            "sources": [run.to_dict() for run in runs],
        }

        self.last_run = report

        return report

    def _discover(self, source: NewsSource) -> DiscoveryResult:

        try:
            return self.discovery.run(source, topics=list(TOPICS))
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
