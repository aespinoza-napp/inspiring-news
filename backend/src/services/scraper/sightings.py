"""
When ingestion first saw each article URL, and when its feed says it was
published.

The lake records when an article was fetched and analysed; nothing
recorded when the system first *knew* about it, or the feed's own
publication time, which discovery read and threw away. Between them
they split "how long did it take us to get this article" into the part
the source and our polling cost (published -> first seen) and the part
our own queue costs (first seen -> fetched). src/services/freshness.py
reads both.

Only ingestion records here: it is the path by which an article enters
the pipeline unasked. The probe, the /sources check and the labelling
batch also discover, but what they see is not queued, and counting them
would make an article look "seen" long before ingestion ever chose it.

Keyed by comparable_url (host and path), so a tracking parameter does
not make a second sighting. The first sighting is kept; a later one only
fills a feed time the first lacked.

Like RequestStats: in memory until src/main.py attaches a file at
startup (tests get no file), written after every change through a
temporary file, and fail-soft - a full disk must not stop an ingestion.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from src.services.scraper.article_stats import comparable_url

logger = logging.getLogger(__name__)


def _iso(value: datetime | None) -> str | None:

    if value is None:
        return None

    if value.tzinfo is None:
        value = value.astimezone()

    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


class Sightings:

    def __init__(self, path: Path | None = None):

        self._lock = threading.Lock()
        self._entries: dict[str, dict] = {}
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
                self._entries = dict(data.get("sightings") or {})
            except Exception:
                logger.warning("Could not load sightings from %s", self._path, exc_info=True)

    def record(
        self,
        urls: list[str],
        *,
        source_id: str,
        method: str | None,
        published: dict[str, datetime] | None = None,
        seen_at: datetime | None = None,
    ) -> int:
        """Notes each URL not seen before; returns how many were new."""

        seen = _iso(seen_at or datetime.now(timezone.utc))
        published = published or {}
        new = 0

        with self._lock:

            for url in urls:

                key = comparable_url(url)
                feed_time = _iso(published.get(url))
                entry = self._entries.get(key)

                if entry is None:
                    self._entries[key] = {
                        "url": url,
                        "sourceId": source_id,
                        "firstSeenAt": seen,
                        "feedPublishedAt": feed_time,
                        "method": method,
                    }
                    new += 1
                elif entry.get("feedPublishedAt") is None and feed_time:
                    entry["feedPublishedAt"] = feed_time

            self._save_locked()

        return new

    def all(self) -> dict[str, dict]:

        with self._lock:
            return {key: dict(entry) for key, entry in self._entries.items()}

    def reset(self) -> None:

        with self._lock:
            self._entries = {}
            self._save_locked()

    def _save_locked(self) -> None:

        path = self._path

        if path is None:
            return

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f"{path.name}.tmp")
            temporary.write_text(json.dumps({"sightings": self._entries}), encoding="utf-8")
            os.replace(temporary, path)
        except Exception:
            logger.warning("Could not save sightings to %s", path, exc_info=True)


# The process-wide one, attached to the lake by src/main.py.
sightings = Sightings()
