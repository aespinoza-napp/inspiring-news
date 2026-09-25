"""
How many requests the scraper has sent to each domain, and what came of
them.

Every strategy used to report failure the same way - `None` - and log a
warning nobody reads. A source whose pages had started timing out, or
returning 403, or coming back as a cookie wall with forty words of text,
looked exactly like a source nobody had asked for. These counts are what
make "the scraper is failing for X" a thing that can be seen rather than
guessed.

One store for the whole process, because four different places construct
their own ExtractorService (the analyzer, the evidence scraper, the
enrichment page and the unwired ingestion Scraper) and a count split four
ways answers nothing.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from logging import getLogger
from pathlib import Path
from urllib.parse import urlsplit

logger = getLogger(__name__)


class Outcome(str, Enum):
    """What one extraction attempt came to. Only `ok` produced an article."""

    OK = "ok"

    # Fetched and parsed, but shorter than the run's min_body_length - a
    # paywall stub, a cookie wall, a gallery page.
    TOO_SHORT = "too_short"

    # Fetched, but the strategy found no article text in it at all.
    NO_CONTENT = "no_content"

    # The server answered with a 4xx or 5xx.
    HTTP_ERROR = "http_error"

    TIMEOUT = "timeout"

    CONNECTION_ERROR = "connection_error"

    # Refused by our own URL guard - never sent. Counted anyway, because a
    # source that resolves to a private address is a source that cannot
    # be scraped from here.
    BLOCKED = "blocked"

    # Anything else a strategy raised.
    ERROR = "error"

    # The strategy cannot run here at all - a browser that is not
    # installed. Says nothing about the page.
    UNAVAILABLE = "unavailable"


class Purpose(str, Enum):
    """Why the page was fetched."""

    # An article posted to /analyze.
    ARTICLE = "article"

    # A web search hit being read as evidence for a claim.
    EVIDENCE = "evidence"

    # The enrichment page inspecting a URL.
    ENRICHMENT = "enrichment"

    # Discovery-driven scraping of a configured source.
    INGESTION = "ingestion"

    # Reading a source's feed (or its homepage) to find article URLs.
    DISCOVERY = "discovery"

    # The /sources page checking that a configured source still extracts.
    SOURCE_CHECK = "source_check"

    # A sample article read by the source probe, to see whether the
    # source can be scraped at all today (services/scraper/source_probe.py).
    PROBE = "probe"


def domain_of(url: str) -> str:
    """Host without `www.`, lowercased; the URL itself if it has none."""

    host = urlsplit(url.strip()).netloc.lower()

    return host.removeprefix("www.") or url.strip()


@dataclass
class DomainStats:

    domain: str

    # One per page wanted. Outcomes, purposes and the success rate are
    # per extraction.
    extractions: int = 0

    # HTTP requests actually sent. Not the same number: BeautifulSoup
    # reads the page trafilatura already fetched (0 requests), a browser
    # fetches again (1 more), and a URL the guard refuses sends none.
    requests: int = 0

    outcomes: dict[str, int] = field(default_factory=dict)

    purposes: dict[str, int] = field(default_factory=dict)

    # Which strategy produced the article, for the extractions that
    # produced one - "which step of the cascade does the work here".
    strategies: dict[str, int] = field(default_factory=dict)

    # How often each strategy was tried at all.
    tried: dict[str, int] = field(default_factory=dict)

    # Configured source ids this domain was fetched as ("web" for a URL
    # that belongs to no configured source).
    sources: list[str] = field(default_factory=list)

    total_ms: float = 0.0

    last_at: str | None = None

    last_url: str | None = None

    last_outcome: str | None = None

    last_status: int | None = None

    # The most recent failure, kept separately from the most recent
    # attempt: once a source recovers, "why did it fail" must still be
    # answerable.
    last_error: str | None = None

    last_error_at: str | None = None

    def to_dict(self) -> dict:

        ok = self.outcomes.get(Outcome.OK.value, 0)

        return {
            "domain": self.domain,
            "extractions": self.extractions,
            "requests": self.requests,
            "ok": ok,
            "failed": self.extractions - ok,
            "successRate": ok / self.extractions if self.extractions else None,
            "outcomes": dict(self.outcomes),
            "purposes": dict(self.purposes),
            "strategies": dict(self.strategies),
            "tried": dict(self.tried),
            "sources": list(self.sources),
            "avgMs": self.total_ms / self.extractions if self.extractions else None,
            "lastAt": self.last_at,
            "lastUrl": self.last_url,
            "lastOutcome": self.last_outcome,
            "lastStatus": self.last_status,
            "lastError": self.last_error,
            "lastErrorAt": self.last_error_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DomainStats":

        requests = int(data.get("requests", 0))

        # Files written before the cascade counted one request per
        # extraction and had no separate figure.
        extractions = int(data.get("extractions", requests))

        return cls(
            domain=data["domain"],
            extractions=extractions,
            requests=requests,
            outcomes=dict(data.get("outcomes") or {}),
            purposes=dict(data.get("purposes") or {}),
            strategies=dict(data.get("strategies") or {}),
            tried=dict(data.get("tried") or {}),
            sources=list(data.get("sources") or []),
            total_ms=float(data.get("avgMs") or 0.0) * extractions,
            last_at=data.get("lastAt"),
            last_url=data.get("lastUrl"),
            last_outcome=data.get("lastOutcome"),
            last_status=data.get("lastStatus"),
            last_error=data.get("lastError"),
            last_error_at=data.get("lastErrorAt"),
        )


def _bump(counter: dict[str, int], key: str) -> None:

    counter[key] = counter.get(key, 0) + 1


class RequestStats:
    """
    Per-domain request counts, thread-safe, optionally persisted.

    Without a file it counts in memory for the life of the process (and
    that is what tests get). With one attached - src/main.py does it at
    startup, next to the job journal - the counts are loaded from it and
    rewritten after every request, so a restart does not reset them.
    Writing is fail-soft: a full disk must not stop the fetch it counts.
    """

    def __init__(self, path: Path | None = None):

        self._lock = threading.Lock()
        self._domains: dict[str, DomainStats] = {}
        self._since = _now()
        self._path: Path | None = None

        if path is not None:
            self.attach(path)

    def attach(self, path: Path | None) -> None:
        """Persist to `path` from now on, starting from what it holds."""

        with self._lock:

            self._path = Path(path) if path is not None else None

            if self._path is None or not self._path.exists():
                return

            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._domains = {
                    entry["domain"]: DomainStats.from_dict(entry)
                    for entry in data.get("domains", [])
                }
                self._since = data.get("since") or self._since
            except Exception:
                logger.warning("Could not load scraper stats from %s", self._path, exc_info=True)

    def record(
        self,
        url: str,
        outcome: Outcome,
        purpose: Purpose | str = Purpose.ARTICLE,
        strategy: str = "",
        source_id: str | None = None,
        status: int | None = None,
        error: str | None = None,
        elapsed_ms: float = 0.0,
        sent: int = 1,
        tried: list[str] | None = None,
    ) -> None:
        """
        One extraction: its final outcome, the strategy that produced the
        article (empty when none did), every strategy tried on the way,
        and how many HTTP requests it took.
        """

        at = _now()
        domain = domain_of(url)
        outcome_value = Outcome(outcome).value
        purpose_value = purpose.value if isinstance(purpose, Purpose) else str(purpose)

        with self._lock:

            stats = self._domains.setdefault(domain, DomainStats(domain=domain))

            stats.extractions += 1
            stats.requests += max(sent, 0)
            stats.total_ms += max(elapsed_ms, 0.0)

            _bump(stats.outcomes, outcome_value)
            _bump(stats.purposes, purpose_value)

            if strategy and outcome_value == Outcome.OK.value:
                _bump(stats.strategies, strategy)

            for name in tried if tried is not None else ([strategy] if strategy else []):
                _bump(stats.tried, name)

            if source_id and source_id not in stats.sources:
                stats.sources.append(source_id)

            stats.last_at = at
            stats.last_url = url
            stats.last_outcome = outcome_value
            stats.last_status = status

            if outcome_value != Outcome.OK.value:
                stats.last_error = error or outcome_value
                stats.last_error_at = at

            # Inside the lock: saved outside it, two concurrent records
            # could land in either order and the older count win.
            self._save(self._snapshot_locked())

    def snapshot(self) -> dict:

        with self._lock:
            return self._snapshot_locked()

    def reset(self) -> None:

        with self._lock:
            self._domains = {}
            self._since = _now()
            self._save(self._snapshot_locked())

    def _snapshot_locked(self) -> dict:

        domains = sorted(
            (stats.to_dict() for stats in self._domains.values()),
            key=lambda entry: entry["extractions"],
            reverse=True,
        )

        outcomes: dict[str, int] = {}

        for entry in domains:
            for key, count in entry["outcomes"].items():
                outcomes[key] = outcomes.get(key, 0) + count

        extractions = sum(entry["extractions"] for entry in domains)
        ok = outcomes.get(Outcome.OK.value, 0)

        strategies: dict[str, int] = {}

        for entry in domains:
            for key, count in entry["strategies"].items():
                strategies[key] = strategies.get(key, 0) + count

        return {
            "since": self._since,
            "totals": {
                "domains": len(domains),
                "extractions": extractions,
                "requests": sum(entry["requests"] for entry in domains),
                "ok": ok,
                "failed": extractions - ok,
                "outcomes": outcomes,
                "strategies": strategies,
            },
            "domains": domains,
        }

    def _save(self, snapshot: dict) -> None:
        """
        Written to a temporary file and swapped in, so a crash mid-write
        leaves the previous counts rather than half a JSON document.
        """

        path = self._path

        if path is None:
            return

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f"{path.name}.tmp")
            temporary.write_text(json.dumps(snapshot), encoding="utf-8")
            os.replace(temporary, path)
        except Exception:
            logger.warning("Could not save scraper stats to %s", path, exc_info=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# The process-wide store. Module-level for the same reason job_store is:
# the extractors that record into it are constructed in four places.
request_stats = RequestStats()
