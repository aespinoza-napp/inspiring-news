"""
Which analysed article came from which trend (docs/decisions/trends.md).

A trending round sends its chosen articles to analysis as ordinary jobs:
the analysis knows nothing of trends, by design - a trend's article is an
article, and virality never enters a verdict. The writing flow does need
to know: a draft from a trend is told the trend, looks for a constructive
angle (services/trends/angles.py) and may show the video a person gave.
So when a trending round is queued, each article's trend card is noted
here, keyed by comparable_url like the sightings, and a draft looks its
article up.

Like Sightings: in memory until src/main.py attaches a file at startup
(tests get no file), written through a temporary file after each change,
and fail-soft - a full disk must not stop a round being queued. The
latest card for a URL wins: queued again from a later trend, the article
is that trend's story now.
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


class TrendLedger:

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
                self._entries = dict(data.get("articles") or {})
            except Exception:
                logger.warning("Could not load the trend ledger from %s", self._path, exc_info=True)

    def remember(self, url: str, card: dict, round_id: str | None = None) -> None:
        """Note that `url` was sent to analysis as the story of the trend `card`."""

        with self._lock:
            self._entries[comparable_url(url)] = {
                "url": url,
                "trend": dict(card),
                "roundId": round_id,
                "queuedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            self._save_locked()

    def find(self, url: str | None) -> dict | None:
        """The trend card `url` was queued under; None for an article no trend brought."""

        if not url:
            return None

        with self._lock:
            entry = self._entries.get(comparable_url(url))

        return dict(entry["trend"]) if entry else None

    def all(self) -> dict[str, dict]:

        with self._lock:
            return {key: dict(entry) for key, entry in self._entries.items()}

    def _save_locked(self) -> None:

        path = self._path

        if path is None:
            return

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f"{path.name}.tmp")
            temporary.write_text(json.dumps({"articles": self._entries}, ensure_ascii=False), encoding="utf-8")
            os.replace(temporary, path)
        except Exception:
            logger.warning("Could not save the trend ledger to %s", path, exc_info=True)


# The process-wide one, attached to the lake by src/main.py.
trend_ledger = TrendLedger()
