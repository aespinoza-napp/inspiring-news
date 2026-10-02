"""
The reader's feed, kept in step with the lake.

A publishable article is one the pipeline admitted, checked and decided
on: its exploitation record says `publishable` (validation passed, verdict
not FALSE or MISLEADING - see DataLakeRepository). The feed is those, one
per article, newest first.

What a request costs. /scraper/articles reads all three layers, processed
included, on every poll; the processed layer carries an embedding and the
scraped evidence pages, hundreds of KB a record. The feed must not repeat
that. So:

- each request lists the exploitation layer's *stamps* (record id ->
  mtime and size, from the directory alone - JsonFileLakeBackend.stamps);
  when they match the last request's, nothing is read at all;
- when they differ, only the records that are new or changed are read -
  the exploitation record and, if it is publishable, its processed record
  once, for the per-claim tally on the card. An exploitation record is
  written after its processed record is final (AnalysisService.
  _store_verified), so a card never goes stale;
- a backend that cannot give stamps falls back to listing the layer per
  request - still without re-reading any processed record already seen.

An article view reads three records (exploitation, processed, raw) by id.
Ids are deterministic per (layer, article, run), so no search is needed.

Process-local and rebuilt on start, like every other cache here: the lake
is the record, this is a view of it.
"""

from __future__ import annotations

import threading
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from logging import getLogger

from src.models.storage.lineage import DataLayer, build_record_id
from src.services.reader.views import SourceNames, article_view, card, reader_id

logger = getLogger(__name__)

DEFAULT_PAGE = 20


@dataclass(frozen=True)
class _Entry:
    """One exploitation record, as much of it as the feed needs."""

    record_id: str

    reader_id: str

    article_id: str

    run_id: str

    publishable: bool

    # When this run was stored: decides which of several runs over the
    # same article is the current one.
    checked_at: float

    # Feed order: when it was published, or when it was checked if the
    # extractor found no date.
    sort_at: float

    topic: str | None

    language: str | None

    # Built only for a publishable record - the only kind the feed shows -
    # so a rejected article never costs a read of its processed record.
    card: dict | None


def _timestamp(value) -> float:
    """
    Seconds since the epoch, for ordering. Lake timestamps are a mix: the
    pipeline's own are naive local time (`datetime.now()`), a feed's
    publication date is often timezone-aware, and comparing the two
    raises. A naive one is read as local time, which is what it is.
    """

    if not value:
        return 0.0

    try:
        moment = datetime.fromisoformat(str(value))
    except ValueError:
        return 0.0

    try:
        return moment.astimezone().timestamp()
    except (OverflowError, OSError, ValueError):
        return 0.0


def _same(left: str | None, right: str) -> bool:

    return (left or "").casefold() == right.casefold()


def _facet(values, key: str) -> list[dict]:

    counts = Counter(value for value in values if value)

    return [
        {key: value, "count": count}
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


class ReaderIndex:

    def __init__(self, lake, names: SourceNames | None = None):

        self.lake = lake
        self.names = names or SourceNames()

        # One refresh at a time; requests arriving meanwhile wait for it
        # and then find nothing left to read.
        self._lock = threading.Lock()

        self._stamps: dict | None = None
        self._seen: dict[str, object] = {}
        self._entries: dict[str, _Entry | None] = {}

        # The current run of every article (publishable or not), by
        # reader id, and the publishable ones in feed order.
        self._latest: dict[str, _Entry] = {}
        self._feed: list[_Entry] = []

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def feed(
        self,
        topic: str | None = None,
        language: str | None = None,
        offset: int = 0,
        limit: int = DEFAULT_PAGE,
    ) -> dict:

        with self._lock:
            self._refresh()
            published = list(self._feed)
            analysed = len(self._latest)

        in_language = [
            entry for entry in published if not language or _same(entry.language, language)
        ]

        on_topic = [
            entry for entry in published if not topic or _same(entry.topic, topic)
        ]

        selected = [entry for entry in in_language if not topic or _same(entry.topic, topic)]

        return {
            "total": len(selected),
            "offset": offset,
            "limit": limit,
            "items": [entry.card for entry in selected[offset:offset + limit]],
            # Each facet is counted under the *other* filter, so a topic
            # chip says how many articles clicking it would show.
            "topics": _facet((entry.topic for entry in in_language), "topic"),
            "languages": _facet((entry.language for entry in on_topic), "language"),
            # For an honest empty state: "nothing analysed yet" and
            # "analysed, but none passed" are different things to fix.
            "lake": {"analysed": analysed, "publishable": len(published)},
        }

    def article(self, article_id: str) -> dict | None:
        """
        One article's reader payload, or None when there is no published
        article with that id - including one whose latest check withdrew
        it, whatever an earlier run decided.
        """

        with self._lock:
            self._refresh()
            entry = self._latest.get(article_id)

        if entry is None or not entry.publishable:
            return None

        exploitation = self.lake.get(DataLayer.EXPLOITATION, entry.record_id)

        if exploitation is None:
            return None

        processed = self.lake.get(
            DataLayer.PROCESSED,
            build_record_id(DataLayer.PROCESSED, entry.article_id, entry.run_id),
        )

        raw = self.lake.get(
            DataLayer.RAW,
            build_record_id(DataLayer.RAW, entry.article_id, entry.run_id),
        )

        return article_view(exploitation, processed, raw, self.names)

    # ------------------------------------------------------------------
    # Keeping in step
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        """Caller holds the lock."""

        stamps = self.lake.stamps(DataLayer.EXPLOITATION)

        if stamps is None:
            self._refresh_from_listing()
            return

        if stamps == self._stamps:
            return

        for record_id, stamp in stamps.items():

            if self._seen.get(record_id) == stamp:
                continue

            document = self.lake.get(DataLayer.EXPLOITATION, record_id)

            # Removed between the listing and the read: the next listing
            # will not have it either.
            if document is None:
                continue

            self._entries[record_id] = self._entry(document)
            self._seen[record_id] = stamp

        for record_id in set(self._entries) - set(stamps):
            del self._entries[record_id]
            self._seen.pop(record_id, None)

        self._stamps = stamps

        self._rebuild()

    def _refresh_from_listing(self) -> None:

        documents = {
            document.get("record_id"): document
            for document in self.lake.list(DataLayer.EXPLOITATION)
            if document.get("record_id")
        }

        for record_id, document in documents.items():
            if record_id not in self._entries:
                self._entries[record_id] = self._entry(document)

        for record_id in set(self._entries) - set(documents):
            del self._entries[record_id]

        self._rebuild()

    def _entry(self, document: dict) -> _Entry | None:

        lineage = document.get("lineage") or {}

        url = document.get("url") or lineage.get("source_url")
        article_id = document.get("article_id") or lineage.get("article_id")
        run_id = lineage.get("run_id")

        # A record that cannot be placed is skipped, not fatal: one odd
        # file must not empty the feed. Its stamp is still remembered, so
        # it is not re-read on every request.
        if not (url and article_id and run_id):
            logger.warning("Reader skips exploitation record %s: no url, article or run id",
                           document.get("record_id"))
            return None

        publishable = bool(document.get("publishable"))

        checked_at = _timestamp(lineage.get("produced_at"))

        processed = None

        if publishable:
            processed = self.lake.get(
                DataLayer.PROCESSED,
                build_record_id(DataLayer.PROCESSED, article_id, run_id),
            )

        return _Entry(
            record_id=document.get("record_id") or "",
            reader_id=reader_id(url),
            article_id=article_id,
            run_id=run_id,
            publishable=publishable,
            checked_at=checked_at,
            sort_at=_timestamp(document.get("published_at")) or checked_at,
            topic=document.get("primary_topic"),
            language=document.get("language"),
            card=card(document, processed, self.names) if publishable else None,
        )

    def _rebuild(self) -> None:

        latest: dict[str, _Entry] = {}

        for entry in self._entries.values():

            if entry is None:
                continue

            current = latest.get(entry.reader_id)

            # The newest run of an article is its current state. An
            # article re-checked and now FALSE leaves the feed, even
            # though an older run once published it.
            if current is None or (entry.checked_at, entry.record_id) > (
                current.checked_at,
                current.record_id,
            ):
                latest[entry.reader_id] = entry

        self._latest = latest

        self._feed = sorted(
            (entry for entry in latest.values() if entry.publishable),
            key=lambda entry: (entry.sort_at, entry.checked_at, entry.reader_id),
            reverse=True,
        )
