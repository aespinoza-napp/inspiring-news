"""
The web search, answered from a file when it has been asked before
(`cli run --search-cache FILE`, 2026-11-06).

Two searched runs differ by 6-9 points on the custom set's train half with
every retrieval figure alike: the pages differ, not the recall. On 10 AVeriTeC
train claims it was worse than that. The query "Boracay photos taken" found a
source taking a side in one run and none in the next, an hour apart, so a change
to the question plan could not be told from SearXNG's mood. With this, a query
asked before gets the answer it got then, and only a query that changed is
searched again: two plans compared on one cache differ by what they asked.

What it does not fix: the pages are still fetched live (they change far less
than the result lists), and the first run to ask a query fixes its answer for
every run after it. A cache is for comparing plans on train, never for a
reported figure: a run made with one says so in its label, which `cli run`
requires.

Only answers with results are kept, as the in-memory cache does: an empty one
is most often every engine suspended.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from src.services.search import SearxngClient


class CachedSearxngClient(SearxngClient):

    def __init__(self, path: Path, **kwargs):

        super().__init__(**kwargs)

        self.path = Path(path)
        self._file_lock = threading.Lock()
        self._stored: dict[str, list[dict]] = {}

        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    entry = json.loads(line)
                    self._stored[self._key(entry["query"], entry.get("language"))] = entry["results"]

    @staticmethod
    def _key(query: str, language: str | None) -> str:
        return f"{language or ''}\t{query}"

    def _fetch_or_fall_back(self, query: str, language: str | None) -> list[dict]:

        key = self._key(query, language)

        with self._file_lock:
            stored = self._stored.get(key)

        if stored is not None:
            self._route.value = "recorded"
            return stored

        results = super()._fetch_or_fall_back(query, language)

        if results:
            with self._file_lock:
                self._stored[key] = results
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as file:
                    file.write(json.dumps({"query": query, "language": language, "results": results}, ensure_ascii=False) + "\n")

        return results

    @property
    def size(self) -> int:
        return len(self._stored)
