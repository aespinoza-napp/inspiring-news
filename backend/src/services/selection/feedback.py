"""
What a person rejected and chose, teaching the ranking.

Asked for on 2026-11-24: some stories that appear in a round should never
be chosen - nothing in them is positive impact - and marking them should
change what the ranking offers next. A person marks a candidate **Not for
us** on /discover (with reasons, and if they like "never from this site");
the stories they record or send are what they chose. Both are kept here,
per edition, across rounds: `lake/stats/selection/feedback/examples.json`,
beside the rounds.

What it does to a new round of the same edition (selection_service.py):

1. **A rejected article never comes back**, by host and path, and a
   **blocked site's** articles are left out. Both are the person's own
   word, so they need no measuring.
2. **Stories like what was rejected are lowered**, from three rejected and
   three chosen: the *lean* of a candidate is how much nearer it comes to
   the average of the rejected stories than to the average of the chosen
   ones (relevance feedback: Rocchio's centroids, cosine, bge-m3), and a
   share of it (LEAN_WEIGHTS, more as the examples grow) is taken off the
   story's own reading before the ranking scales it (ranking.news_part).
   The four weights are untouched.
3. **Clearly like what was rejected is left out** - a lean over
   LEAVE_OUT_LEAN - only once there are LEAVE_OUT_MINIMUM examples. Below
   that the average of a few stories wanders, and leaving out would cost
   good stories (the measurement below).

Measured 2026-11-24 (`experiments feedback`,
data/evaluation/experiments/feedback/20261124T121248Z; docs/decisions/
selection.md, "What you reject teaches the ranking"): the hand-labelled
candidates of 6, 9 and 13 Oct the screen keeps, examples from one day and
candidates of the others, 200 draws a size. Nearest-neighbour similarity
to a rejected story does not generalise: no candidate of another day came
within 0.60 of any rejected story. The lean does. Telling the
worth-offering from the rest, the story part alone scores AUC 0.759;
lowered by a quarter of the lean, 0.784 with 3 + 3 examples; by half,
0.807 with 10 + 5 and 0.824 with 40 + 20. By half with only 3 or 5
rejected, the clearly positive ranked a little worse than with the story
alone (0.848 against 0.856), hence a quarter until 10 + 5. Leaving out
over 0.08 with 40 + 20: 19% of the not worth offering, 0.1 clearly
positive on average and 1 at worst; with 10 + 5 it would have lost up to
11 of 22.

The labels it was measured on are an AI's (Claude's), not the person's;
the person's own rejections are what it runs on.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from logging import getLogger
from pathlib import Path
from typing import Callable

import numpy as np

from src.services.scraper.article_stats import comparable_url
from src.services.scraper.request_stats import domain_of
from src.services.selection.mission_screen import screen_text

logger = getLogger(__name__)

# How much of the lean comes off the story's reading (impact - off-mission,
# before ranking.NEWS_RANGE scales it), by how many rejected and chosen
# examples there are: the first step met wins. A quarter was never worse
# than the story alone on either measure at any size; half was better from
# 10 + 5 on, and with fewer cost the clearly positive a little.
LEAN_WEIGHTS = ((10, 5, 0.5), (3, 3, 0.25))

# Lowered from this many rejected and chosen examples on: the smallest
# measured, and on average already better than the story alone.
LOWER_MINIMUM = (3, 3)

# Left out over this lean, from this many rejected and chosen examples on.
LEAVE_OUT_LEAN = 0.08
LEAVE_OUT_MINIMUM = (40, 20)

Embed = Callable[[list[str]], np.ndarray]


def _now() -> str:

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _unit(vector: np.ndarray) -> np.ndarray:

    norm = float(np.linalg.norm(vector))

    return vector / norm if norm else vector


@dataclass(frozen=True)
class Feedback:
    """One edition's examples, as the ranking reads them: two averages."""

    rejected: np.ndarray
    chosen: np.ndarray
    rejected_count: int
    chosen_count: int

    def lean(self, vector: np.ndarray | None) -> float | None:
        """Cosine to the rejected average minus cosine to the chosen one; None with nothing read."""

        if vector is None:
            return None

        unit = _unit(np.asarray(vector, dtype=float))

        return float(unit @ self.rejected - unit @ self.chosen)

    @property
    def weight(self) -> float:
        """The share of the lean taken off the story's reading, for this many examples."""

        return weight_for(self.rejected_count, self.chosen_count)

    @property
    def leaves_out(self) -> bool:

        return self.rejected_count >= LEAVE_OUT_MINIMUM[0] and self.chosen_count >= LEAVE_OUT_MINIMUM[1]

    def leave_out(self, lean: float | None) -> bool:
        """Clearly like what was rejected, and enough examples to say so."""

        return self.leaves_out and lean is not None and lean > LEAVE_OUT_LEAN


def weight_for(rejected: int, chosen: int) -> float:
    """LEAN_WEIGHTS' share for this many examples; 0 below every step."""

    for at_least_rejected, at_least_chosen, weight in LEAN_WEIGHTS:
        if rejected >= at_least_rejected and chosen >= at_least_chosen:
            return weight

    return 0.0


# The rule's constants, as a round and the page record and show them.
_RULE = {
    "weights": [{"rejected": r, "chosen": c, "weight": w} for r, c, w in LEAN_WEIGHTS],
    "leaveOutLean": LEAVE_OUT_LEAN,
    "lowerMinimum": {"rejected": LOWER_MINIMUM[0], "chosen": LOWER_MINIMUM[1]},
    "leaveOutMinimum": {"rejected": LEAVE_OUT_MINIMUM[0], "chosen": LEAVE_OUT_MINIMUM[1]},
}


def described(rejected: int, chosen: int, blocked: int, applied: bool, status: str) -> dict:
    """
    What a round records of the feedback it was ranked with: `status` off
    (nothing taught), ok, or unavailable (inference/ could not be reached,
    so nothing was lowered); `lowered` whether the lean applied, which
    needs LOWER_MINIMUM examples; `leavesOut` whether it could leave out.
    """

    return {
        "status": status,
        "rejected": rejected,
        "chosen": chosen,
        "blockedSites": blocked,
        "lowered": applied,
        # The share of the lean this round took off, 0 when not lowered.
        "weight": weight_for(rejected, chosen) if applied else 0.0,
        "leavesOut": applied and rejected >= LEAVE_OUT_MINIMUM[0] and chosen >= LEAVE_OUT_MINIMUM[1],
        **_RULE,
    }


class SelectionFeedback:
    """
    The examples, per edition, in one JSON file beside the rounds.

    `folder` is asked each time (the rounds' own, attached by src/main.py),
    so tests that give the rounds a tmp_path get a file there and the
    others none. `embed` turns texts into vectors (inference/'s bge-m3);
    each example's vector is kept in memory by its text, so a round embeds
    only examples it has not seen.
    """

    def __init__(self, folder: Callable[[], Path | None], embed: Embed | None = None, rounds=None):

        self._folder = folder
        self._embed = embed
        self._rounds = rounds
        self._lock = threading.Lock()
        self._state: dict | None = None
        self._vectors: dict[str, np.ndarray] = {}

    # ------------------------------------------------------------------
    # What the person said
    # ------------------------------------------------------------------

    def reject(self, round_: dict, candidate: dict, reasons: list[str], note: str | None, site: bool) -> dict:
        """
        `candidate` of `round_` is not for us; `site`: nothing more from its
        host in this edition. Saying it again replaces what was said.
        """

        edition = round_.get("edition") or "positive"
        key = comparable_url(candidate["url"])
        host = domain_of(candidate["url"])

        with self._lock:

            state = self._load_locked()
            state["rejected"] = [row for row in state["rejected"] if not (row["key"] == key and row["edition"] == edition)]
            state["rejected"].append({
                "url": candidate["url"],
                "key": key,
                "host": host,
                "title": candidate.get("title"),
                "summary": candidate.get("summary"),
                "sourceName": candidate.get("sourceName"),
                "edition": edition,
                "reasons": reasons,
                "note": note,
                "roundId": round_["id"],
                "at": _now(),
            })

            state["blockedSites"] = [row for row in state["blockedSites"] if not (row["host"] == host and row["edition"] == edition and row.get("url") == candidate["url"])]

            if site and not any(row["host"] == host and row["edition"] == edition for row in state["blockedSites"]):
                state["blockedSites"].append({"host": host, "edition": edition, "url": candidate["url"], "roundId": round_["id"], "at": _now()})

            self._save_locked(state)

        return self.summary(edition)

    def forget(self, edition: str, url: str | None = None, host: str | None = None) -> list[dict]:
        """
        Takes back a rejection (by `url`) and the site blocked with it, or a
        blocked site (by `host`). Returns what was taken back ([]: nothing),
        so the caller can clear the rounds it came from.
        """

        with self._lock:

            state = self._load_locked()
            gone: list[dict] = []

            def drop(rows: list[dict], matches) -> list[dict]:
                kept = []
                for row in rows:
                    (gone.append(row) if matches(row) else kept.append(row))
                return kept

            if url:
                key = comparable_url(url)
                state["rejected"] = drop(state["rejected"], lambda row: row["key"] == key and row["edition"] == edition)
                state["blockedSites"] = drop(state["blockedSites"], lambda row: row.get("url") == url and row["edition"] == edition)

            if host:
                state["blockedSites"] = drop(state["blockedSites"], lambda row: row["host"] == host and row["edition"] == edition)

            if gone:
                self._save_locked(state)

        return gone

    def choose(self, round_: dict, urls: list[str], by: str) -> None:
        """The person's picks (`by`: "recorded" or "sent"), the chosen side of the examples."""

        edition = round_.get("edition") or "positive"
        by_url = {candidate["url"]: candidate for candidate in round_.get("candidates") or []}

        with self._lock:

            state = self._load_locked()
            known = {(row["key"], row["edition"]) for row in state["chosen"]}

            for url in urls:
                candidate = by_url.get(url)
                key = comparable_url(url)
                if candidate is None or (key, edition) in known:
                    continue
                known.add((key, edition))
                state["chosen"].append({
                    "url": url,
                    "key": key,
                    "title": candidate.get("title"),
                    "summary": candidate.get("summary"),
                    "edition": edition,
                    "by": by,
                    "roundId": round_["id"],
                    "at": _now(),
                })

            self._save_locked(state)

    # ------------------------------------------------------------------
    # What the ranking reads
    # ------------------------------------------------------------------

    def rejected_keys(self, edition: str) -> set[str]:

        with self._lock:
            return {row["key"] for row in self._load_locked()["rejected"] if row["edition"] == edition}

    def blocked_hosts(self, edition: str) -> set[str]:

        with self._lock:
            return {row["host"] for row in self._load_locked()["blockedSites"] if row["edition"] == edition}

    def counts(self, edition: str) -> tuple[int, int, int]:
        """(rejected, chosen, blocked sites) in `edition`."""

        with self._lock:
            state = self._load_locked()
            return (
                sum(row["edition"] == edition for row in state["rejected"]),
                sum(row["edition"] == edition for row in state["chosen"]),
                sum(row["edition"] == edition for row in state["blockedSites"]),
            )

    def feedback(self, edition: str) -> Feedback | None:
        """
        The two averages for `edition`, or None below LOWER_MINIMUM. Raises
        what `embed` raises (InferenceUnavailable) when an example has no
        vector yet and inference/ cannot be reached.
        """

        with self._lock:
            state = self._load_locked()
            rejected = [row for row in state["rejected"] if row["edition"] == edition]
            chosen = [row for row in state["chosen"] if row["edition"] == edition]

        if len(rejected) < LOWER_MINIMUM[0] or len(chosen) < LOWER_MINIMUM[1]:
            return None

        # Both sides in one request, and only what has not been embedded yet.
        self._embed_missing(rejected + chosen)

        rejected_vectors = self._cached(rejected)
        chosen_vectors = self._cached(chosen)

        if not len(rejected_vectors) or not len(chosen_vectors):
            return None

        return Feedback(
            rejected=_unit(np.mean([_unit(v) for v in rejected_vectors], axis=0)),
            chosen=_unit(np.mean([_unit(v) for v in chosen_vectors], axis=0)),
            rejected_count=len(rejected_vectors),
            chosen_count=len(chosen_vectors),
        )

    def summary(self, edition: str) -> dict:
        """What the page lists: every rejection and blocked site of `edition`, and how many were chosen."""

        with self._lock:
            state = self._load_locked()
            rejected = [row for row in state["rejected"] if row["edition"] == edition]
            blocked = [row for row in state["blockedSites"] if row["edition"] == edition]
            chosen = sum(row["edition"] == edition for row in state["chosen"])

        newest = lambda rows: sorted(rows, key=lambda row: row.get("at") or "", reverse=True)

        return {
            "edition": edition,
            "rejected": [
                {key: row.get(key) for key in ("url", "host", "title", "sourceName", "reasons", "note", "roundId", "at")}
                for row in newest(rejected)
            ],
            "blockedSites": [{key: row.get(key) for key in ("host", "url", "roundId", "at")} for row in newest(blocked)],
            "chosen": chosen,
            **_RULE,
        }

    # ------------------------------------------------------------------

    def _embed_missing(self, rows: list[dict]) -> None:

        texts = [screen_text(row.get("title"), row.get("summary")) for row in rows]
        missing = [text for text in dict.fromkeys(texts) if text and text not in self._vectors]

        if missing and self._embed is not None:
            for text, vector in zip(missing, np.asarray(self._embed(missing))):
                self._vectors[text] = np.asarray(vector, dtype=float)

    def _cached(self, rows: list[dict]) -> list[np.ndarray]:

        texts = [screen_text(row.get("title"), row.get("summary")) for row in rows]

        return [self._vectors[text] for text in texts if text and text in self._vectors]

    def _path(self) -> Path | None:

        folder = self._folder()

        # In a folder of its own: everything *.json beside the rounds is
        # read as a round (rounds.SelectionRounds.list, experiments.load_rounds).
        return Path(folder) / "feedback" / "examples.json" if folder is not None else None

    def _load_locked(self) -> dict:

        if self._state is not None:
            return self._state

        state = {"rejected": [], "chosen": [], "blockedSites": []}
        path = self._path()

        if path is not None and path.exists():
            try:
                state.update(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                logger.warning("Could not read %s; starting with no feedback", path, exc_info=True)
        elif self._rounds is not None:
            # First use: what was already chosen on /discover counts, so a
            # rejection is weighed against the person's picks from the start.
            state["chosen"] = _chosen_in(self._rounds.list(limit=100_000))

        self._state = state

        return state

    def _save_locked(self, state: dict) -> None:

        self._state = state
        path = self._path()

        if path is None:
            return

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f"{path.name}.tmp")
            temporary.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(temporary, path)
        except OSError:
            logger.warning("Could not save the selection feedback to %s", path, exc_info=True)


def _chosen_in(rounds: list[dict]) -> list[dict]:
    """Every pick a person recorded or sent in the rounds kept, once per article and edition."""

    rows, seen = [], set()

    for round_ in sorted(rounds, key=lambda round_: round_.get("startedAt") or ""):

        edition = round_.get("edition") or "positive"
        by_url = {candidate["url"]: candidate for candidate in round_.get("candidates") or []}
        picks = [("recorded", url) for url in (round_.get("personSelection") or {}).get("urls") or []]
        picks += [("sent", url) for url in (round_.get("queued") or {}).get("urls") or []]

        for by, url in picks:
            key = comparable_url(url)
            candidate = by_url.get(url)
            if candidate is None or (key, edition) in seen:
                continue
            seen.add((key, edition))
            rows.append({
                "url": url, "key": key, "title": candidate.get("title"), "summary": candidate.get("summary"),
                "edition": edition, "by": by, "roundId": round_["id"], "at": round_.get("startedAt"),
            })

    return rows
