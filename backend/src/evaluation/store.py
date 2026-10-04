"""
The append-only JSONL file a benchmark writes its results into.

Shared by the verification harness (runner.py) and the writing benchmark
(writing.py), because both have the same three needs and getting any of
them wrong costs hours of model time:

- **A finished unit is on disk before the next one starts paying.** Each
  write is one line, then flush, then `os.fsync`: a crash at claim 90
  loses claim 90, not claims 1-89.
- **A crash mid-write leaves a torn last line.** It is cut off on load
  (the file is truncated back to the last complete line), so the unit is
  simply not done and runs again - and the next append does not glue a
  fresh record onto half of an old one.
- **Records are keyed, not ordered.** Units run concurrently and finish
  in any order; the latest record for a key wins, so a retried error is
  appended rather than edited in place.

A line that is not JSON *and* is not the last one is not a torn write:
something else edited the file. That is refused rather than guessed at.

docs/decisions/evaluation.md §Run layout, cache and resume.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable


class ResultsFileError(RuntimeError):
    """The results file is damaged somewhere a crash cannot explain."""


class ResultsFile:

    def __init__(self, path: Path):

        self.path = Path(path)

        self._lock = threading.Lock()

        # How many torn lines the last load() cut off: 0 or 1. Reported in
        # the run's session log, so a resumed crash is visible afterwards.
        self.torn = 0

    def load(self) -> list[dict]:
        """
        Every complete record, in file order. Truncates a torn last line
        as a side effect, so the next append starts on a clean line.
        """

        self.torn = 0

        if not self.path.exists():
            return []

        data = self.path.read_bytes()

        records: list[dict] = []

        offset = 0

        lines = data.split(b"\n")

        for number, raw in enumerate(lines, start=1):

            if raw.strip():

                try:
                    records.append(json.loads(raw.decode("utf-8")))
                except (ValueError, UnicodeDecodeError) as exc:

                    if any(rest.strip() for rest in lines[number:]):
                        raise ResultsFileError(
                            f"{self.path}:{number} is not JSON and is not the "
                            "last line, so it is not a torn write. Refusing to "
                            "guess which records are good."
                        ) from exc

                    self._truncate(offset)
                    self.torn = 1

                    return records

            offset += len(raw) + 1

        # A complete last record with no newline after it: the crash fell
        # between the two. Keep the record, finish the line.
        if data and not data.endswith(b"\n"):
            with self.path.open("ab") as handle:
                handle.write(b"\n")

        return records

    def latest(self, key: Callable[[dict], str]) -> dict[str, dict]:
        """The last record written for each key."""

        return {key(record): record for record in self.load()}

    def append(self, record: dict) -> None:

        line = json.dumps(record, ensure_ascii=False, default=str) + "\n"

        with self._lock:

            self.path.parent.mkdir(parents=True, exist_ok=True)

            # newline="\n": text mode on Windows would write \r\n, and the
            # loader counts bytes per line to know where to truncate.
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())

    def set_aside(self) -> Path | None:
        """
        `--fresh`: move the current file out of the way rather than delete
        it. Hours of model time are not thrown away by one flag.
        """

        if not self.path.exists():
            return None

        stamp = datetime.now().strftime("%Y%m%dT%H%M%S")

        target = self.path.with_name(f"{self.path.stem}.replaced-{stamp}{self.path.suffix}")

        self.path.replace(target)

        return target

    def _truncate(self, offset: int) -> None:

        with self.path.open("r+b") as handle:
            handle.truncate(offset)


def write_json(path: Path, value) -> None:
    """A whole JSON document, written to a temporary file and moved into place."""

    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_name(path.name + ".tmp")

    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    temporary.replace(path)


def read_json(path: Path):

    return json.loads(Path(path).read_text(encoding="utf-8"))
