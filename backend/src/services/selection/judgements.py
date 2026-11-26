"""
Every judgement made on /discover, kept in the lake as one dataset:
`lake/judgements/`.

Asked for on 2026-11-26: the editor's choices - what they sent, what they
recorded to compare with the AI, what they marked not for us, and why -
were spread over one file per round (`lake/stats/selection/`, 2.2 MB for
37 rounds, mostly discovery's own record of every source) and the
feedback's examples (`stats/selection/feedback/examples.json`), all inside
the Docker volume. Reading them meant opening every round; turning them
into a dataset meant knowing the shape of each. Now one folder holds them,
and needs nothing beside it:

- `events.jsonl` - **append-only**, one line per judgement as it is made
  (KINDS): `sent`, `recorded`, `not_for_us`, `undone` (taken back on its
  round), `forgotten` (taken back from the list of what was taught),
  `unblocked` (a site no longer left out), and `ai` (the AI's scores, so
  the person and the AI are read from one file). Before a round's first
  judgement, and again whenever its list grew, a `shown` line records
  every candidate shown then, in order, with its reading and its rank:
  what was judged from, and so what was *not* chosen. Never rewritten - an
  undo is a line of its own, so the history stays readable.
- `dataset.jsonl` and `dataset.csv` - rebuilt from `events.jsonl` alone
  after every judgement (build_dataset): one row per candidate shown in a
  round a person judged, labelled `chosen`, `not_for_us` or `not_chosen`,
  with the reasons and note given, the candidate's own text, the ranking's
  scores and the AI's. Derived, so a change of columns is a rebuild, never
  a migration, and a copy of the folder carries everything.

Rounds from before the log are turned into events once (backfill): the
first time the app starts on a lake with rounds and no `events.jsonl`,
each judgement at the time its round recorded it, marked `backfilled`.
What was undone before then is not in them: a round keeps only its
current marks.

Like the rounds, only the real app attaches the folder (src/main.py), so
tests never write into the lake. Every write is fail-soft: the round is
already saved when a judgement is logged, and a full disk must not turn a
click on /discover into an error.

The rounds and the feedback's examples stay what the step reads; this is
the record of what was said, for reading and for datasets.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import threading
from datetime import datetime, timezone
from logging import getLogger
from pathlib import Path

from src.services.scraper.article_stats import comparable_url
from src.services.scraper.request_stats import domain_of

logger = getLogger(__name__)

SCHEMA = 1

EVENTS = "events.jsonl"
DATASET = "dataset.jsonl"
DATASET_CSV = "dataset.csv"

KINDS = ("shown", "sent", "recorded", "not_for_us", "undone", "forgotten", "unblocked", "ai")

# A person's judgements: a round with one of these is in the dataset.
PERSON_KINDS = ("sent", "recorded", "not_for_us", "undone", "forgotten", "unblocked")

LABELS = ("chosen", "not_for_us", "not_chosen")

# What a shown candidate keeps of the round's record: its own text and
# where it came from. `reading` and `rank` are copied whole below.
CANDIDATE_FIELDS = (
    "url", "title", "summary", "source", "sourceName", "language", "groups",
    "publishedAt", "image", "method", "otherGroup", "sameStoryAs",
)

TREND_FIELDS = ("name", "signal", "signalName", "position")

# The CSV's columns, in order; nested values are flattened with a prefix
# and lists joined by LIST_SEPARATOR.
CSV_COLUMNS = (
    "roundId", "roundStartedAt", "edition", "groups", "lens", "topicEmphasis", "shown",
    "position", "label", "chosenBy", "reasons", "note", "blockSite", "judgedAt",
    "url", "key", "host", "title", "summary", "sourceName", "source", "language", "publishedAt", "image",
    "trend_name", "trend_signal",
    "reading_impact", "reading_topic", "reading_nearestTopic", "reading_off", "reading_nearestOff", "reading_groupFit",
    "rank_score", "rank_news", "rank_topic", "rank_record", "rank_reliability", "rank_lean",
    "ai_score", "ai_reason", "ai_picked", "ai_model",
)

LIST_SEPARATOR = "|"


def _now() -> str:

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _edition(round_: dict) -> str:

    return round_.get("edition") or "positive"


def _event_id(kind: str, round_id: str | None, subject, at: str) -> str:

    return hashlib.sha1(json.dumps([kind, round_id, subject, at], ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def round_context(round_: dict) -> dict:
    """What every line says of the round it was made in."""

    emphasis = ((round_.get("ranking") or {}).get("topicEmphasis") or {}).get("applied")

    return {
        "id": round_.get("id"),
        "startedAt": round_.get("startedAt"),
        "groups": list(round_.get("groups") or []),
        "lens": round_.get("lens"),
        "topicEmphasis": emphasis,
    }


def candidate_row(candidate: dict, position: int) -> dict:
    """One shown candidate as `shown` keeps it: 1-based position, its text, its reading and rank."""

    row: dict = {"position": position}

    for field in CANDIDATE_FIELDS:
        if candidate.get(field) is not None:
            row[field] = candidate[field]

    row["key"] = comparable_url(candidate["url"])
    row["host"] = domain_of(candidate["url"])

    for field in ("reading", "rank"):
        if isinstance(candidate.get(field), dict):
            row[field] = dict(candidate[field])

    trend = candidate.get("trend")

    if isinstance(trend, dict):
        row["trend"] = {field: trend.get(field) for field in TREND_FIELDS}

    return row


# ----------------------------------------------------------------------
# The dataset, from the events alone
# ----------------------------------------------------------------------


def build_dataset(events: list[dict]) -> list[dict]:
    """
    One row per candidate shown in a round a person judged, oldest round
    first and in the order shown. A round's list is its last `shown` line
    (lists only grow, by `more`); a candidate marked not for us that no
    `shown` line lists is added from its own line. Chosen beats not for us,
    which the step refuses anyway; a mark undone or forgotten is gone -
    `forgotten` is logged on the round the mark was made in, the one the
    feedback's row names.
    """

    rounds: dict[str, dict] = {}

    def state(event: dict) -> dict | None:

        context = event.get("round") or {}
        round_id = context.get("id")

        if not round_id:
            return None

        return rounds.setdefault(round_id, {
            "context": context,
            "edition": event.get("edition") or "positive",
            "shown": [],
            "extra": {},
            "chosen": {},
            "marks": {},
            "ai": None,
            "judged": False,
            "judgedAt": None,
        })

    for event in events:

        kind = event.get("kind")
        current = state(event)

        if current is None:
            continue

        if kind in PERSON_KINDS:
            current["judged"] = True
            current["judgedAt"] = event.get("at")

        if kind == "shown":
            current["shown"] = list(event.get("candidates") or [])

        elif kind in ("sent", "recorded"):
            for pick in event.get("picks") or []:
                chosen = current["chosen"].setdefault(pick["url"], {"by": [], "reasons": [], "note": None, "at": None})
                if kind not in chosen["by"]:
                    chosen["by"].append(kind)
                chosen["reasons"] += [code for code in pick.get("reasons") or [] if code not in chosen["reasons"]]
                chosen["note"] = pick.get("note") or chosen["note"]
                chosen["at"] = event.get("at")

        elif kind == "not_for_us":
            candidate = event.get("candidate") or {}
            url = candidate.get("url")
            if url:
                current["marks"][url] = {
                    "reasons": list(event.get("reasons") or []),
                    "note": event.get("note"),
                    "site": bool(event.get("site")),
                    "at": event.get("at"),
                    "key": candidate.get("key") or comparable_url(url),
                }
                current["extra"].setdefault(url, candidate)

        elif kind in ("undone", "forgotten"):
            current["marks"].pop(event.get("url"), None)

        elif kind == "unblocked":
            mark = current["marks"].get(event.get("url"))
            if mark is not None:
                mark["site"] = False

        elif kind == "ai":
            current["ai"] = event

    rows: list[dict] = []

    for current in sorted(rounds.values(), key=lambda item: item["context"].get("startedAt") or ""):

        if not current["judged"]:
            continue

        shown = list(current["shown"])
        listed = {row["url"] for row in shown}
        shown += [row for url, row in current["extra"].items() if url not in listed]

        ai = current["ai"] or {}
        ai_scores = {row["url"]: row for row in ai.get("scored") or []}
        ai_picks = set(ai.get("picks") or [])
        context = current["context"]
        edition = current["edition"]

        for row in shown:

            url = row["url"]
            key = row.get("key") or comparable_url(url)
            chosen = current["chosen"].get(url)
            mark = current["marks"].get(url)

            if chosen is not None:
                label, by, reasons, note, at = "chosen", chosen["by"], chosen["reasons"], chosen["note"], chosen["at"]
            elif mark is not None:
                label, by, reasons, note, at = "not_for_us", [], mark["reasons"], mark["note"], mark["at"]
            else:
                label, by, reasons, note, at = "not_chosen", [], [], None, None

            scored = ai_scores.get(url)

            rows.append({
                "schema": SCHEMA,
                "roundId": context.get("id"),
                "roundStartedAt": context.get("startedAt"),
                "edition": edition,
                "groups": context.get("groups") or [],
                "lens": context.get("lens"),
                "topicEmphasis": context.get("topicEmphasis"),
                "shown": len(shown),
                "position": row.get("position"),
                "label": label,
                "chosenBy": by,
                "reasons": reasons,
                "note": note,
                "blockSite": mark["site"] if label == "not_for_us" else None,
                "judgedAt": at,
                "url": url,
                "key": key,
                "host": row.get("host") or domain_of(url),
                **{field: row.get(field) for field in ("title", "summary", "sourceName", "source", "language", "publishedAt", "image")},
                "trend": row.get("trend"),
                "reading": row.get("reading"),
                "rank": row.get("rank"),
                "ai": (
                    {"score": scored.get("score") if scored else None, "reason": scored.get("reason") if scored else None,
                     "picked": url in ai_picks, "model": ai.get("model")}
                    if ai else None
                ),
            })

    return rows


def _flat(value) -> str | float | int | None:

    if isinstance(value, list):
        return LIST_SEPARATOR.join(str(item) for item in value)

    if isinstance(value, bool):
        return "true" if value else "false"

    return value


def dataset_csv(rows: list[dict]) -> str:
    """The dataset as CSV (CSV_COLUMNS): nested values prefixed, lists joined by `|`."""

    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(CSV_COLUMNS), extrasaction="ignore", lineterminator="\n")
    writer.writeheader()

    for row in rows:

        flat = {key: _flat(value) for key, value in row.items() if not isinstance(value, dict)}

        for prefix in ("trend", "reading", "rank", "ai"):
            for key, value in (row.get(prefix) or {}).items():
                flat[f"{prefix}_{key}"] = _flat(value)

        writer.writerow(flat)

    return out.getvalue()


def dataset_jsonl(rows: list[dict]) -> str:

    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)


# ----------------------------------------------------------------------
# The log
# ----------------------------------------------------------------------


class SelectionJudgements:

    def __init__(self, folder: Path | None = None):

        self._lock = threading.Lock()
        self._folder: Path | None = Path(folder) if folder is not None else None
        self._events: list[dict] | None = None
        # How many candidates each round's last `shown` line listed.
        self._shown: dict[str, int] = {}

    def attach(self, folder: Path | None) -> None:
        """Write to `folder` from now on; None stops writing (and keeps nothing)."""

        with self._lock:
            self._folder = Path(folder) if folder is not None else None
            self._events = None
            self._shown = {}

    def folder(self) -> Path | None:

        with self._lock:
            return self._folder

    # ------------------------------------------------------------------
    # What was said
    # ------------------------------------------------------------------

    def picked(self, round_: dict, kind: str, urls: list[str], why: dict | None = None, at: str | None = None, **extra) -> None:
        """`kind` "sent" or "recorded": the person's picks of `round_`, with the reasons and notes `why` holds."""

        why = why or {}
        by_url = {candidate["url"]: candidate for candidate in round_.get("candidates") or []}
        at = at or _now()

        picks = [
            {
                "url": url,
                "title": (by_url.get(url) or {}).get("title"),
                "reasons": list((why.get("reasons") or {}).get(url) or []),
                "note": (why.get("notes") or {}).get(url),
            }
            for url in urls
        ]

        self._record(round_, {"kind": kind, "picks": picks, **{k: v for k, v in extra.items() if v is not None}}, at, list(urls))

    def rejected(self, round_: dict, candidate: dict, reasons: list[str], note: str | None, site: bool, at: str | None = None) -> None:
        """`candidate` of `round_` is not for us; said again, the later line is what holds."""

        position = next((i for i, c in enumerate(round_.get("candidates") or [], 1) if c["url"] == candidate["url"]), None)

        self._record(round_, {
            "kind": "not_for_us",
            "candidate": candidate_row(candidate, position),
            "reasons": list(reasons or []),
            "note": note,
            "site": bool(site),
        }, at or _now(), candidate["url"])

    def undone(self, round_: dict, url: str) -> None:

        self._record(round_, {"kind": "undone", "url": url, "key": comparable_url(url)}, _now(), url)

    def taken_back(self, edition: str, row: dict, round_: dict | None) -> None:
        """
        One row the feedback's forget gave back: a rejection (it has a
        `key`) or a blocked site. `round_` is the round it was made in, when
        that is still held.
        """

        url = row.get("url")
        context = round_ if round_ is not None else {"id": row.get("roundId"), "edition": edition}

        if "key" in row:
            event = {"kind": "forgotten", "url": url, "key": row["key"]}
        else:
            event = {"kind": "unblocked", "url": url, "host": row.get("host")}

        self._record(context, event, _now(), [url, row.get("host")], show=round_ is not None)

    def ai(self, round_: dict, state: dict) -> None:
        """The AI's finished selection of `round_`: every score, and its picks."""

        if state.get("status") != "done":
            return

        self._record(round_, {
            "kind": "ai",
            "scorer": state.get("scorer"),
            "model": state.get("model"),
            "picks": [row["url"] for row in state.get("picks") or []],
            "scored": [{"url": row["url"], "score": row.get("score"), "reason": row.get("reason")} for row in state.get("scored") or []],
        }, state.get("finishedAt") or _now(), "ai")

    # ------------------------------------------------------------------
    # Reading back
    # ------------------------------------------------------------------

    def events(self) -> list[dict]:

        with self._lock:
            return list(self._load_locked())

    def dataset(self, edition: str | None = None) -> list[dict]:

        rows = build_dataset(self.events())

        return [row for row in rows if edition is None or row["edition"] == edition]

    def summary(self, edition: str | None = None, limit: int = 50) -> dict:
        """What the API lists: the counts, and the newest lines without their candidate lists."""

        events = [event for event in self.events() if edition is None or event.get("edition") == edition]
        rows = self.dataset(edition)

        kinds = {kind: 0 for kind in KINDS}
        for event in events:
            kinds[event.get("kind")] = kinds.get(event.get("kind"), 0) + 1

        labels = {label: 0 for label in LABELS}
        for row in rows:
            labels[row["label"]] += 1

        def brief(event: dict) -> dict:
            if event.get("kind") == "shown":
                return {**{k: v for k, v in event.items() if k != "candidates"}, "candidates": len(event.get("candidates") or [])}
            if event.get("kind") == "ai":
                return {**{k: v for k, v in event.items() if k != "scored"}, "scored": len(event.get("scored") or [])}
            return event

        folder = self.folder()

        return {
            "schema": SCHEMA,
            "edition": edition,
            "folder": str(folder) if folder is not None else None,
            "files": {"events": EVENTS, "dataset": DATASET, "csv": DATASET_CSV},
            "events": len(events),
            "kinds": kinds,
            "rounds": len({row["roundId"] for row in rows}),
            "rows": len(rows),
            "labels": labels,
            "latest": [brief(event) for event in reversed(events[-limit:])] if limit else [],
        }

    # ------------------------------------------------------------------
    # The rounds from before the log
    # ------------------------------------------------------------------

    def backfill(self, rounds: list[dict]) -> int:
        """
        Every judgement the rounds hold, as events, when the folder has no
        `events.jsonl` yet; else nothing. Returns how many lines it wrote.
        """

        with self._lock:

            path = self._path_locked(EVENTS)

            if path is None or path.exists():
                return 0

            events = events_from_rounds(rounds)

            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_name(f"{path.name}.tmp")
                temporary.write_text("".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events), encoding="utf-8")
                os.replace(temporary, path)
            except OSError:
                logger.warning("Could not write the judgements' backfill to %s", path, exc_info=True)
                return 0

            self._events = None
            self._load_locked()

            try:
                self._rebuild_locked()
            except OSError:
                logger.warning("Could not write the judgements' dataset beside %s", path, exc_info=True)

        logger.info("Judgements: %d events from %d rounds written to %s", len(events), len(rounds), path)

        return len(events)

    # ------------------------------------------------------------------

    def _record(self, round_: dict, event: dict, at: str, subject, show: bool = True) -> None:

        try:
            with self._lock:

                if self._path_locked(EVENTS) is None:
                    return

                self._load_locked()

                round_id = round_.get("id")
                candidates = round_.get("candidates") or []
                lines = []

                # What it was judged from, first, when the list is new or grew.
                if show and round_id and len(candidates) > self._shown.get(round_id, 0):
                    lines.append(shown_event(round_, at))

                lines.append({
                    "schema": SCHEMA,
                    "id": _event_id(event["kind"], round_id, subject, at),
                    "at": at,
                    "edition": _edition(round_),
                    "round": round_context(round_) if show else {"id": round_id},
                    "by": "ai" if event["kind"] == "ai" else "person",
                    **event,
                })

                self._append_locked(lines)
                self._rebuild_locked()

        except Exception:
            logger.warning("Could not log a judgement of round %s", round_.get("id"), exc_info=True)

    def _path_locked(self, name: str) -> Path | None:

        return self._folder / name if self._folder is not None else None

    def _load_locked(self) -> list[dict]:

        if self._events is not None:
            return self._events

        events: list[dict] = []
        path = self._path_locked(EVENTS)

        if path is not None and path.exists():

            for line in path.read_text(encoding="utf-8").splitlines():

                if not line.strip():
                    continue

                try:
                    events.append(json.loads(line))
                except ValueError:
                    # A torn last line (the process killed mid-append) must
                    # not make the whole log unreadable.
                    logger.warning("Skipping an unreadable line of %s", path)

        self._events = events
        self._shown = {}

        for event in events:
            if event.get("kind") == "shown" and (event.get("round") or {}).get("id"):
                self._shown[event["round"]["id"]] = len(event.get("candidates") or [])

        return events

    def _append_locked(self, lines: list[dict]) -> None:

        path = self._path_locked(EVENTS)
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("a", encoding="utf-8") as handle:
            handle.write("".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines))
            handle.flush()

        self._events.extend(lines)

        for line in lines:
            if line["kind"] == "shown":
                self._shown[line["round"]["id"]] = len(line.get("candidates") or [])

    def _rebuild_locked(self) -> None:

        rows = build_dataset(self._events or [])

        for name, text in ((DATASET, dataset_jsonl(rows)), (DATASET_CSV, dataset_csv(rows))):
            path = self._path_locked(name)
            temporary = path.with_name(f"{path.name}.tmp")
            temporary.write_text(text, encoding="utf-8")
            os.replace(temporary, path)


def shown_event(round_: dict, at: str) -> dict:

    candidates = round_.get("candidates") or []

    return {
        "schema": SCHEMA,
        "id": _event_id("shown", round_.get("id"), len(candidates), at),
        "at": at,
        "edition": _edition(round_),
        "round": round_context(round_),
        "by": None,
        "kind": "shown",
        "candidates": [candidate_row(candidate, position) for position, candidate in enumerate(candidates, 1)],
    }


def events_from_rounds(rounds: list[dict]) -> list[dict]:
    """
    The judgements each round holds, as the log would have written them:
    its list once, at its first judgement, then the AI's finished scores,
    the recorded choice, what was sent and every current mark, in time
    order, each marked `backfilled`.
    """

    events: list[dict] = []

    for round_ in sorted(rounds, key=lambda round_: round_.get("startedAt") or ""):

        if not round_.get("id"):
            continue

        context = round_context(round_)
        edition = _edition(round_)
        by_url = {candidate["url"]: candidate for candidate in round_.get("candidates") or []}
        said: list[tuple[str, dict]] = []

        def line(kind: str, at: str, subject, **fields) -> tuple[str, dict]:
            return at, {
                "schema": SCHEMA, "id": _event_id(kind, round_["id"], subject, at), "at": at, "edition": edition,
                "round": context, "by": "ai" if kind == "ai" else "person", "kind": kind, **fields, "backfilled": True,
            }

        ai = round_.get("aiSelection") or {}

        if ai.get("status") == "done":
            at = ai.get("finishedAt") or round_.get("startedAt") or ""
            said.append(line(
                "ai", at, "ai", scorer=ai.get("scorer"), model=ai.get("model"),
                picks=[row["url"] for row in ai.get("picks") or []],
                scored=[{"url": row["url"], "score": row.get("score"), "reason": row.get("reason")} for row in ai.get("scored") or []],
            ))

        for kind, record, extra in (
            ("recorded", round_.get("personSelection") or {}, ("blind",)),
            ("sent", round_.get("queued") or {}, ("selectedBy",)),
        ):
            if not record.get("urls"):
                continue
            at = record.get("at") or round_.get("startedAt") or ""
            picks = [
                {"url": url, "title": (by_url.get(url) or {}).get("title"),
                 "reasons": list((record.get("reasons") or {}).get(url) or []), "note": (record.get("notes") or {}).get(url)}
                for url in record["urls"]
            ]
            said.append(line(kind, at, list(record["urls"]), picks=picks, **{key: record[key] for key in extra if key in record}))

        for position, candidate in enumerate(round_.get("candidates") or [], 1):
            mark = (round_.get("rejected") or {}).get(candidate["url"])
            if mark is None:
                continue
            at = mark.get("at") or round_.get("startedAt") or ""
            said.append(line(
                "not_for_us", at, candidate["url"], candidate=candidate_row(candidate, position),
                reasons=list(mark.get("reasons") or []), note=mark.get("note"), site=bool(mark.get("site")),
            ))

        if not said:
            continue

        said.sort(key=lambda item: item[0])
        first = said[0][0]
        listed = shown_event(round_, first)
        listed["backfilled"] = True

        events.append(listed)
        events += [event for _, event in said]

    # Across rounds, in the order they were said; a round's list before its
    # judgements, since a sort by time keeps ties in place.
    events.sort(key=lambda event: event.get("at") or "")

    return events


# The process-wide one, attached to the lake by src/main.py.
selection_judgements = SelectionJudgements()


# ----------------------------------------------------------------------
# Building the folder from rounds kept elsewhere
# ----------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """
    The folder from a copy of the rounds (`docker cp
    docker-backend-1:/app/data/lake/stats/selection <dir>`), or a running
    backend's dataset fetched over its API, written to `--out`.

        uv run python -m src.services.selection.judgements --rounds <dir> --out <dir>
        uv run python -m src.services.selection.judgements --backend http://127.0.0.1:8000 --out <dir>
    """

    parser = argparse.ArgumentParser(description=main.__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--rounds", type=Path, help="a folder of round files (lake/stats/selection)")
    source.add_argument("--backend", help="a running backend; its own lake's judgements are fetched")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)

    if args.rounds:
        rounds = []
        for path in sorted(args.rounds.glob("*.json")):
            try:
                rounds.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                logger.warning("Could not read %s", path)
        if (args.out / EVENTS).exists():
            raise SystemExit(f"{args.out / EVENTS} exists: the log is never rewritten. Choose another --out.")
        log = SelectionJudgements(args.out)
        written = log.backfill(rounds)
        summary = log.summary(limit=0)
        print(f"{written} events from {len(rounds)} rounds; {summary['rows']} rows in {summary['rounds']} judged rounds: {summary['labels']}")

    else:
        import requests

        from src.config.settings import settings

        key = settings.STORAGE_API_KEY.get_secret_value() if settings.STORAGE_API_KEY else None
        headers = {"X-API-Key": key} if key else {}
        base = args.backend.rstrip("/")

        for name, path in ((EVENTS, "/ingest/judgements/events"), (DATASET, "/ingest/judgements/dataset?format=jsonl"),
                           (DATASET_CSV, "/ingest/judgements/dataset?format=csv")):
            response = requests.get(f"{base}{path}", headers=headers, timeout=60)
            response.raise_for_status()
            (args.out / name).write_text(response.text, encoding="utf-8")

        print(f"Written {EVENTS}, {DATASET} and {DATASET_CSV} from {base}")

    print(f"In {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
