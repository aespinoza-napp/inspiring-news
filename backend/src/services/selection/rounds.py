"""
Every candidate round, kept: what was discovered, what the AI picked and
why, what a person sent to analysis in the end.

A round is the record the paper needs from the selection step - how
often the AI and the editor agree, how many candidates a topic yields,
how many picks survive admission - so it is written to disk as it
changes, one JSON file per round, rather than held only in memory:
`lake/stats/selection/<roundId>.json`. Like the sightings and the
scraper stats, only the real app attaches the folder (src/main.py), so
tests never write into the lake.
"""

from __future__ import annotations

import json
import os
import threading
from logging import getLogger
from pathlib import Path

logger = getLogger(__name__)

# Rounds held in memory. Older ones are still on disk, read back on demand.
MEMORY = 50


class SelectionRounds:

    def __init__(self, folder: Path | None = None):

        self._lock = threading.Lock()
        self._rounds: dict[str, dict] = {}
        self._folder: Path | None = Path(folder) if folder is not None else None

    def attach(self, folder: Path | None) -> None:
        """Persist to `folder` from now on."""

        with self._lock:
            self._folder = Path(folder) if folder is not None else None

    def save(self, round_: dict) -> None:

        with self._lock:

            self._rounds[round_["id"]] = round_

            while len(self._rounds) > MEMORY:
                self._rounds.pop(next(iter(self._rounds)))

            self._write_locked(round_)

    def get(self, round_id: str) -> dict | None:

        with self._lock:

            if round_id in self._rounds:
                return self._rounds[round_id]

            path = self._path_locked(round_id)

        if path is None or not path.exists():
            return None

        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.warning("Could not read selection round %s", path, exc_info=True)
            return None

    def list(self, limit: int = 50) -> list[dict]:
        """The newest rounds first, from disk when attached, else from memory."""

        with self._lock:
            folder = self._folder
            in_memory = list(self._rounds.values())

        if folder is None or not folder.exists():
            rounds = in_memory
        else:
            rounds = []
            for path in folder.glob("*.json"):
                try:
                    rounds.append(json.loads(path.read_text(encoding="utf-8")))
                except (OSError, ValueError):
                    logger.warning("Could not read selection round %s", path, exc_info=True)

        rounds.sort(key=lambda round_: round_.get("startedAt") or "", reverse=True)

        return rounds[:limit]

    # ------------------------------------------------------------------

    def _path_locked(self, round_id: str) -> Path | None:

        # Ids are minted here (uuid hex), but one arrives from a URL path:
        # nothing but hex reaches the file system.
        if self._folder is None or not round_id.isalnum():
            return None

        return self._folder / f"{round_id}.json"

    def _write_locked(self, round_: dict) -> None:

        path = self._path_locked(round_["id"])

        if path is None:
            return

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f"{path.name}.tmp")
            temporary.write_text(json.dumps(round_, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(temporary, path)
        except Exception:
            logger.warning("Could not save selection round to %s", path, exc_info=True)


# The process-wide one, attached to the lake by src/main.py.
selection_rounds = SelectionRounds()
