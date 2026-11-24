"""
The selection step: discovered articles -> up to twenty chosen -> analysis.

POST /ingest sends every new article it finds straight to a full
analysis. A round puts a choice in between:

1. **Candidates** (`create_round`): discovery over the sources of up to
   three topic groups, each article listed with its feed's title and
   summary, best first (src/services/selection/ranking.py). The first
   LISTED are shown; the rest stay in the round as its `reserve`, and
   `show_more` brings up to MAX_LISTED into view. Nothing beyond the feeds
   and section pages is fetched.
2. **Selection**, by a person or by the AI (`start_ai_selection`, an LLM
   reading titles and summaries - src/services/selection/ai_selector.py).
   The AI's picks are a proposal: the person sees them ticked, with the
   reason for each, and can change them.
3. **Queue** (`queue`): at most MAX_SELECTED of the round's candidates
   become ordinary analysis jobs (purpose "ingestion"), and admission and
   the fact-check run on them as on any other.

Every step is written into the round (src/services/selection/rounds.py):
who chose, what the AI had proposed, and how far the two agreed - the
selection step's own measurements.

**What the person rejects teaches the ranking** (2026-11-24, `reject`,
feedback.py): a candidate marked "Not for us" never comes back, a site
blocked never again, and stories like the rejected ones are lowered in
every later round of the edition - left out once there are enough
examples to do it safely.

**The person against the AI** (2026-11-24, `record_person_selection`): a
person can record their own choice of at most COMPARED (five) before
asking the AI, which is then asked for at most five too, so both choose
under the same constraint from the same list. The record says whether it
was blind (no AI proposal on the page), the comparison (`compare`) is kept
with the round, and the photos of both sides' picks are copied beside it
(photos.py). Sending to analysis stays a separate, optional step.

A round can also be **trending** (src/services/trends/trending.py,
docs/decisions/trends.md): its candidates are the articles behind what is
spreading right now - Google's rising searches, r/UpliftingNews' top of
the day, a hashtag a person typed - instead of the sources of some topic
groups. From there it is the same round: the same choice, the same AI
(told the list is trending), the same queue, and each queued article's
trend noted for the writing flow (src/services/trends/ledger.py).
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from logging import getLogger
from typing import Callable

from src.services.inference_client import InferenceUnavailable
from src.services.scraper.article_stats import comparable_url
from src.services.scraper.request_stats import domain_of
from src.services.llms import LLMUnavailableError
from src.services.selection.ai_selector import DEFAULT_MIN_SCORE, AISelector
from src.services.selection.laya_selector import LayaSelector
from src.services.selection.feedback import Feedback, SelectionFeedback, described as described_feedback
from src.services.selection.photos import PhotoKeeper
from src.services.selection.reasons import UnknownReason, cleaned as cleaned_reasons, cleaned_codes, reject_reasons_for
from src.services.selection.rounds import SelectionRounds, selection_rounds as default_rounds

logger = getLogger(__name__)

# The most articles one round sends to analysis. Each is a scrape, an
# enrichment and an LLM call per claim; on the production CPU model one
# article is about three minutes.
MAX_SELECTED = 20

# Candidates a round shows, best first, and the most it shows when asked
# for more. A three-group round finds 60-80; read top to bottom in the
# sources' order, the first twenty of a Science and Society round on
# 2026-10-06 held 8 stories not worth offering, ranked 1. Only what is
# shown can be chosen, by the person or the AI - which also keeps the AI
# selection to two or four calls.
LISTED = 20
MAX_LISTED = 40

# The most a trending round keeps, shown or in reserve, with no topic group,
# one or three (2026-11-23, by the author's request): the best 20 of what
# the signals bring. The groups only order what fits them first, so they
# never change how many there are. Before, a round found 46-54 on 17 Nov,
# showed 20 and kept the rest for "more", up to MAX_LISTED.
# `totals.candidates` still counts everything found.
TRENDING_MAX = 20

# The most a person records, and the AI is asked for, when the two are
# compared (2026-11-24, the author's request: "at most 5, to be
# consistent"). The same cap on both sides, so a disagreement is about
# which stories, not how many. Sending to analysis keeps MAX_SELECTED.
COMPARED = 5

# A person's note on one of their picks: why, in a line or two.
NOTE_CHARS = 300

StartJob = Callable[[str], tuple[str, bool]]


class RoundNotFound(LookupError):
    pass


class SelectionBusy(RuntimeError):
    """An AI selection is already running; the model is shared and slow."""


class InvalidSelection(ValueError):
    pass


class SelectionService:

    def __init__(
        self,
        ingestion,
        selector: AISelector | None = None,
        rounds: SelectionRounds | None = None,
        laya_selector: LayaSelector | None = None,
        trending=None,
        ledger=None,
        photos: PhotoKeeper | None = None,
        feedback: SelectionFeedback | None = None,
    ):
        self.ingestion = ingestion
        self.selector = selector or AISelector()
        # The `scorer: "laya"` option (laya_selector.py): not the default.
        self.laya_selector = laya_selector or LayaSelector()
        self.rounds = rounds if rounds is not None else default_rounds

        # The trending lens (TrendingDiscovery) and where queued trend
        # articles are noted (TrendLedger); None where no trending round is
        # ever made, as in most tests.
        self.trending = trending
        self.ledger = ledger

        # Copies the photos of compared picks (photos.py); None keeps only
        # the links, as in tests, which must not reach anyone's server.
        self.photos = photos

        # What the person rejected and chose (feedback.py), beside the
        # rounds. Its examples are embedded only once there are enough of
        # them to lower anything, so a service nobody taught never asks
        # inference/ for it.
        self.feedback = feedback or SelectionFeedback(self.rounds.folder, embed=_embed, rounds=self.rounds)

        self._lock = threading.Lock()
        self._running: str | None = None

        # Rounds being sent to analysis right now: the AI is not started
        # on one meanwhile, nor one sent while the AI reads it.
        self._sending: set[str] = set()

        # One photo batch at a time: the record's and the AI's could
        # otherwise both copy, and both write, the same round's photos.
        self._photo_lock = threading.Lock()

    # ------------------------------------------------------------------
    # 1. Candidates
    # ------------------------------------------------------------------

    def create_round(
        self,
        groups: list[str],
        source_ids: list[str] | None = None,
        per_source: int = 3,
        listed: int = LISTED,
        topic_emphasis: float | None = None,
        trending: bool = False,
        signal_ids: list[str] | None = None,
        seed: str | None = None,
        search: bool = False,
        edition: str = "positive",
    ) -> dict:
        """
        `edition` (src/config/editions.py) is the round's for good: its
        groups, sources, screen and AI question, and the edition every
        article queued from it is analysed in.

        `topic_emphasis`, 0-1, is how much fitting `groups` weighs against
        positive impact in the order (ranking.py; None: the default) - the
        person's, for this round only, and recorded with it.

        `trending`: the candidates are what is spreading right now - the
        signals in `signal_ids` (None: all) and the person's `seed` - and
        `groups`, which may then be empty, only order what fits them first.
        `per_source` is then articles per trend.
        """

        # Said only of a Devastating round, so a discovery that predates
        # the editions is called exactly as before (like `trending` below).
        told = {"edition": edition} if edition != "positive" else {}

        # What the person taught the ranking in this edition, and only when
        # there is something: the same call as before otherwise.
        feedback, feedback_state = self._feedback_for(edition)

        if feedback is not None:
            told["feedback"] = feedback

        if trending:

            if self.trending is None:
                raise InvalidSelection("Trending rounds are not available here.")

            discovered = self.trending.discover(
                groups=groups, signal_ids=signal_ids, seed=seed,
                per_trend=per_source, search=search, topic_emphasis=topic_emphasis,
                **told,
            )

        else:

            discovered = self.ingestion.discover_candidates(
                groups, source_ids, per_source, topic_emphasis=topic_emphasis,
                **told,
            )

        # Best first already; `totals.candidates` keeps counting all found.
        # What the person rejected, a site they blocked, and - with enough
        # examples - what is clearly like what they rejected, left out
        # before the list is cut, so the reserve fills their places.
        found, left_out = self._left_out(discovered["candidates"], edition, feedback)
        listed = max(1, min(listed, MAX_LISTED))

        if trending:
            found = found[:TRENDING_MAX]

        round_ = {
            "id": uuid.uuid4().hex[:16],
            **discovered,
            "edition": edition,
            "candidates": found[:listed],
            "reserve": found[listed:],
            "aiSelection": None,
            "queued": None,
            # Present from the start: a rejection then only replaces a value
            # while the AI's thread may be writing the round out.
            "rejected": {},
            "feedback": {**feedback_state, "leftOut": len(left_out)},
        }

        if left_out:
            round_["screened"] = list(round_.get("screened") or []) + left_out
            round_["totals"] = {**(round_.get("totals") or {}), "learned": len(left_out)}

        self.rounds.save(round_)

        return round_

    def _feedback_for(self, edition: str) -> tuple[Feedback | None, dict]:
        """
        The person's examples for `edition` as the ranking reads them, and
        what the round records of them. Nothing taught: none, and nothing
        asked of inference/. Unreachable: none, and the round says so - a
        lowering that did not run must not look like one that changed
        nothing.
        """

        rejected, chosen, blocked = self.feedback.counts(edition)

        if not rejected and not blocked:
            return None, described_feedback(rejected, chosen, blocked, False, "off")

        try:
            feedback = self.feedback.feedback(edition)
        except InferenceUnavailable as exc:
            return None, {**described_feedback(rejected, chosen, blocked, False, "unavailable"), "error": str(exc)}
        except Exception as exc:
            logger.warning("Could not read the selection feedback for %s", edition, exc_info=True)
            return None, {**described_feedback(rejected, chosen, blocked, False, "unavailable"), "error": str(exc)}

        return feedback, described_feedback(rejected, chosen, blocked, feedback is not None, "ok")

    def _left_out(self, found: list[dict], edition: str, feedback: Feedback | None) -> tuple[list[dict], list[dict]]:
        """(kept, left out): rejected before, from a blocked site, or clearly like the rejected."""

        rejected = self.feedback.rejected_keys(edition)
        blocked = self.feedback.blocked_hosts(edition)

        if not rejected and not blocked:
            return found, []

        kept, out = [], []

        for candidate in found:

            lean = (candidate.get("rank") or {}).get("lean")

            if comparable_url(candidate["url"]) in rejected:
                why = "rejected"
            elif domain_of(candidate["url"]) in blocked:
                why = "blocked_site"
            elif feedback is not None and feedback.leave_out(lean):
                why = "like_rejected"
            else:
                kept.append(candidate)
                continue

            out.append({
                "url": candidate["url"],
                "source": candidate.get("source"),
                "sourceName": candidate.get("sourceName"),
                "title": candidate.get("title"),
                "offMission": why,
                # The lean itself, for what was left out by it.
                "margin": round(lean, 4) if why == "like_rejected" else None,
                "nearestTopic": None,
            })

        return kept, out

    def show_more(self, round_id: str) -> dict:
        """
        The next of the reserve into view, best first, up to MAX_LISTED
        shown. Not once the round was sent to analysis, and not while the
        AI selection reads the list it would change.
        """

        round_ = self.get(round_id)

        if round_.get("queued"):
            raise InvalidSelection("This round was already sent to analysis.")

        # The AI must choose from the list the person chose from.
        if round_.get("personSelection"):
            raise InvalidSelection("Your choice was recorded from the list as it is; the AI must read the same one.")

        with self._lock:

            if self._running == round_id:
                raise SelectionBusy(round_id)

            room = MAX_LISTED - len(round_["candidates"])
            reserve = round_.get("reserve") or []

            if room > 0 and reserve:
                round_["candidates"] = round_["candidates"] + reserve[:room]
                round_["reserve"] = reserve[room:]
                self.rounds.save(round_)

        return round_

    def get(self, round_id: str) -> dict:

        round_ = self.rounds.get(round_id)

        if round_ is None:
            raise RoundNotFound(round_id)

        return round_

    def list(self, limit: int = 20) -> list[dict]:
        """The newest rounds, summarised: no candidate lists."""

        return [_summary(round_) for round_ in self.rounds.list(limit)]

    # ------------------------------------------------------------------
    # 2. AI selection - in the background: on the CPU model a few
    #    batches are minutes, longer than a request should be held
    # ------------------------------------------------------------------

    def start_ai_selection(
        self,
        round_id: str,
        limit: int = MAX_SELECTED,
        min_score: float = DEFAULT_MIN_SCORE,
        scorer: str = "llm",
    ) -> dict:

        round_ = self.get(round_id)

        if not round_["candidates"]:
            raise InvalidSelection("This round found no candidates to choose from.")

        # Laya was fine-tuned on positive-impact picks: asked about the
        # Devastating edition's candidates it would answer the wrong
        # question with confidence.
        if scorer == "laya" and edition_of(round_) == "devastating":
            raise InvalidSelection("Laya scores positive impact only; use the LLM for a Devastating round.")

        # Against a person's recorded choice, the AI gets the same cap.
        limit = min(limit, COMPARED if round_.get("personSelection") else MAX_SELECTED)

        with self._lock:

            if self._running is not None:
                raise SelectionBusy(self._running)

            if round_id in self._sending:
                raise SelectionBusy(round_id)

            self._running = round_id

        round_["aiSelection"] = {
            "status": "running",
            "startedAt": _now(),
            "limit": limit,
            "minScore": min_score,
            "scorer": scorer,
        }
        self.rounds.save(round_)

        threading.Thread(
            target=self._run_ai_selection,
            args=(round_id, limit, min_score, scorer),
            name="ai-selection",
            daemon=True,
        ).start()

        return round_["aiSelection"]

    def run_ai_selection(self, round_id: str, limit: int, min_score: float, scorer: str = "llm") -> dict:
        """
        The selection itself, on the calling thread. The background
        thread's body; tests call it. `scorer` is "llm" (AISelector, the
        default) or "laya" (LayaSelector).
        """

        round_ = self.get(round_id)
        state = dict(round_.get("aiSelection") or {"startedAt": _now(), "limit": limit, "minScore": min_score})
        state["scorer"] = scorer
        selector = self.laya_selector if scorer == "laya" else self.selector

        try:
            # Said only of a trending round, so a selector that predates
            # the lens is called exactly as before - and only to the LLM:
            # Laya is a classifier, with no prompt to tell it anything.
            told = {"trending": True} if round_.get("lens") == "trending" and scorer != "laya" else {}

            # Likewise said only of a Devastating round.
            if edition_of(round_) == "devastating" and scorer != "laya":
                told["edition"] = "devastating"

            selection = selector.select(round_["candidates"], round_["groups"], limit, min_score, **told)
            state.update(status="done", **selection.to_dict())
        except LLMUnavailableError as exc:
            state.update(status="failed", error=f"The LLM could not be reached: {exc}")
        except InferenceUnavailable as exc:
            state.update(status="failed", error=f"Laya could not be reached in inference/: {exc}")
        except Exception as exc:
            logger.exception("AI selection failed for round %s", round_id)
            state.update(status="failed", error=str(exc))

        state["finishedAt"] = _now()
        round_["aiSelection"] = state

        if round_.get("personSelection"):
            round_["comparison"] = compare(round_)

        self.rounds.save(round_)

        if state["status"] == "done" and round_.get("personSelection"):
            self.keep_photos(round_)

        return state

    def _run_ai_selection(self, round_id: str, limit: int, min_score: float, scorer: str) -> None:

        try:
            self.run_ai_selection(round_id, limit, min_score, scorer)
        finally:
            with self._lock:
                self._running = None

    # ------------------------------------------------------------------
    # 2b. The person's own choice, to compare with the AI's
    # ------------------------------------------------------------------

    def record_person_selection(
        self,
        round_id: str,
        urls: list[str],
        notes: dict[str, str] | None = None,
        reasons: dict[str, list[str]] | None = None,
    ) -> dict:
        """
        A person's choice of at most COMPARED of the round's shown
        candidates, recorded once, with why for each pick if they say:
        reasons from those offered in the round's edition (reasons.py,
        several at once) and a note. Nothing is sent to analysis. `blind` is worked out here, not taken
        from the page: true when no AI proposal had been made (a failed one
        showed nothing). Refused while the AI reads the round - its picks
        would land on a choice recorded as made without them.
        """

        round_ = self.get(round_id)

        chosen = list(dict.fromkeys(urls))
        shown = [candidate["url"] for candidate in round_["candidates"]]

        if not chosen:
            raise InvalidSelection("Choose at least one article.")

        if len(chosen) > COMPARED:
            raise InvalidSelection(f"At most {COMPARED} articles to compare with the AI; {len(chosen)} were chosen.")

        strangers = [url for url in chosen if url not in shown]

        if strangers:
            raise InvalidSelection(f"Not a candidate of this round: {strangers[0]}")

        if round_.get("personSelection"):
            raise InvalidSelection("Your choice for this round is already recorded.")

        _refuse_rejected(round_, chosen)

        why = _why(chosen, notes, reasons, edition_of(round_))

        with self._lock:

            if self._running == round_id:
                raise SelectionBusy(round_id)

            ai = round_.get("aiSelection") or {}

            round_["personSelection"] = {
                "at": _now(),
                "urls": chosen,
                "limit": COMPARED,
                "blind": ai.get("status") != "done",
                # What the person chose from; `more` is refused from now on,
                # so it is also what the AI reads.
                "shown": shown,
                **why,
            }
            round_["comparison"] = compare(round_)
            # Present from the start, so a later copy only replaces a value
            # while another thread may be writing the round out.
            round_.setdefault("photos", {})

            self.rounds.save(round_)

        # What the person chose: the other side of what they rejected.
        self.feedback.choose(round_, chosen, "recorded")

        self.keep_photos(round_)

        return round_["personSelection"]

    def reject(
        self,
        round_id: str,
        url: str,
        reasons: list[str] | None = None,
        note: str | None = None,
        site: bool = False,
        undo: bool = False,
    ) -> dict:
        """
        One of the round's shown candidates is **not for us**, with why
        (reasons.reject_reasons_for, several at once, and a note), and with
        `site`, nothing more from its site in this edition. Said again, it
        replaces what was said; `undo` takes it back. It changes nothing in
        this round's list - the person and the AI keep choosing from the
        same one - and teaches every later round (feedback.py).
        """

        round_ = self.get(round_id)
        candidate = next((c for c in round_["candidates"] if c["url"] == url), None)

        if candidate is None:
            raise InvalidSelection(f"Not a candidate of this round: {url}")

        edition = edition_of(round_)
        picked = set((round_.get("personSelection") or {}).get("urls") or []) | set((round_.get("queued") or {}).get("urls") or [])

        if not undo and url in picked:
            raise InvalidSelection("You chose this one; it cannot also be not for us.")

        try:
            codes = [] if undo else cleaned_codes(reasons, reject_reasons_for(edition))
        except UnknownReason as exc:
            raise InvalidSelection(str(exc))

        with self._lock:

            # A round from before 2026-11-24 has no `rejected` yet: adding
            # the key while the AI's thread writes the round out could break
            # that write, so not then.
            if "rejected" not in round_ and self._running == round_id:
                raise SelectionBusy(round_id)

            marks = dict(round_.get("rejected") or {})

            if undo:
                marks.pop(url, None)
            else:
                marks[url] = {
                    "at": _now(),
                    "reasons": codes,
                    "note": (note or "").strip()[:NOTE_CHARS] or None,
                    "site": bool(site),
                }

            round_["rejected"] = marks

            if round_.get("personSelection") and (round_.get("aiSelection") or {}).get("status") == "done":
                round_["comparison"] = compare(round_)

            self.rounds.save(round_)

        if undo:
            self.feedback.forget(edition, url=url)
        else:
            self.feedback.reject(round_, candidate, codes, marks[url]["note"], marks[url]["site"])

        rejected, chosen, blocked = self.feedback.counts(edition)

        return {"rejected": marks, "counts": {"rejected": rejected, "chosen": chosen, "blockedSites": blocked}}

    def forget(self, edition: str, url: str | None = None, host: str | None = None) -> bool:
        """
        Takes back a rejection or a blocked site from the list of what the
        ranking learned, and its mark on the round it was made in, so that
        round does not show it any more either. False when there was none.
        """

        gone = self.feedback.forget(edition, url=url, host=host)

        for row in gone:

            try:
                round_ = self.get(row["roundId"])
            except (RoundNotFound, KeyError):
                continue

            marks = dict(round_.get("rejected") or {})
            mark = marks.get(row.get("url"))

            if mark is None:
                continue

            if "key" in row:
                marks.pop(row["url"], None)
            else:
                marks[row["url"]] = {**mark, "site": False}

            with self._lock:
                round_["rejected"] = marks
                self.rounds.save(round_)

        return bool(gone)

    def keep_photos(self, round_: dict) -> dict:
        """
        Copies the photos of both sides' picks not yet kept (photos.py),
        and records what became of each on the round as `photos`.
        """

        if self.photos is None:
            return round_.get("photos") or {}

        folder = self.rounds.photo_folder(round_["id"])

        if folder is None:
            return round_.get("photos") or {}

        with self._photo_lock:

            kept = dict(round_.get("photos") or {})
            by_url = {candidate["url"]: candidate for candidate in round_["candidates"]}

            todo = [
                by_url[url]
                for url in dict.fromkeys(_compared_urls(round_))
                if url in by_url and url not in kept and by_url[url].get("image")
            ]

            if not todo:
                return kept

            kept.update(self.photos.keep(folder, todo))
            round_["photos"] = kept
            self.rounds.save(round_)

        return kept

    # ------------------------------------------------------------------
    # 3. Queue
    # ------------------------------------------------------------------

    def queue(
        self,
        round_id: str,
        urls: list[str],
        start_job: StartJob,
        notes: dict[str, str] | None = None,
        reasons: dict[str, list[str]] | None = None,
    ) -> dict:
        """
        `notes` and `reasons`, optional: why each was sent, as with a
        recorded choice - kept with what was sent, so every pick can say why.
        """

        round_ = self.get(round_id)

        chosen = list(dict.fromkeys(urls))
        known = {candidate["url"] for candidate in round_["candidates"]}

        if not chosen:
            raise InvalidSelection("Choose at least one article.")

        if len(chosen) > MAX_SELECTED:
            raise InvalidSelection(f"At most {MAX_SELECTED} articles per round; {len(chosen)} were chosen.")

        strangers = [url for url in chosen if url not in known]

        if strangers:
            raise InvalidSelection(f"Not a candidate of this round: {strangers[0]}")

        if round_.get("queued"):
            raise InvalidSelection("This round was already sent to analysis.")

        _refuse_rejected(round_, chosen)

        why = _why(chosen, notes, reasons, edition_of(round_))

        # Not while the AI reads this round: its picks would land on a
        # selection recorded as the person's alone (selectedBy "user"),
        # and a blind round would be counted wrong in RQ3's comparison.
        with self._lock:

            if self._running == round_id or round_id in self._sending:
                raise SelectionBusy(round_id)

            self._sending.add(round_id)

        try:
            jobs = []

            for url in chosen:
                try:
                    job_id, reused = start_job(url)
                    jobs.append({"url": url, "jobId": job_id, "reused": reused})
                except Exception as exc:
                    logger.warning("Could not queue %s: %s", url, exc)
                    jobs.append({"url": url, "jobId": None, "reused": False, "error": str(exc)})

            round_["queued"] = {
                "at": _now(),
                "urls": chosen,
                "jobs": jobs,
                **_agreement(chosen, round_.get("aiSelection")),
                **why,
            }

            self.rounds.save(round_)

        finally:
            with self._lock:
                self._sending.discard(round_id)

        self.feedback.choose(round_, chosen, "sent")

        # A trend's article is analysed like any other; the draft written
        # from it later needs to know its trend.
        if self.ledger is not None:
            cards = {candidate["url"]: candidate.get("trend") for candidate in round_["candidates"]}
            for job in jobs:
                if job.get("jobId") and cards.get(job["url"]):
                    self.ledger.remember(job["url"], cards[job["url"]], round_id=round_id)

        return round_["queued"]


def _agreement(chosen: list[str], ai: dict | None) -> dict:
    """
    Who chose, and how far the person kept the AI's proposal: the
    selection step's own measurement. `selectedBy` is worked out here,
    not taken from the client, so it cannot claim agreement that was not
    there.
    """

    proposed = [pick["url"] for pick in (ai or {}).get("picks") or []] if (ai or {}).get("status") == "done" else []

    if not proposed:
        return {"selectedBy": "user", "aiProposed": 0, "aiKept": 0, "aiDropped": 0, "userAdded": len(chosen)}

    kept = len(set(chosen) & set(proposed))
    added = len(set(chosen) - set(proposed))
    dropped = len(set(proposed) - set(chosen))

    selected_by = "ai" if not added and not dropped else "ai+user" if kept else "user"

    return {
        "selectedBy": selected_by,
        "aiProposed": len(proposed),
        "aiKept": kept,
        "aiDropped": dropped,
        "userAdded": added,
    }


def compare(round_: dict) -> dict | None:
    """
    The person's recorded choice against the AI's finished one, over the
    list the person chose from; None until both exist. Precision and
    recall are the AI's against the person (of the AI's picks, how many
    the person chose; of the person's, how many the AI did), as in
    src/evaluation/experiments.py `selection`. Kappa is Cohen's, over every
    shown candidate as chosen or not by each. `aiScores` is the AI's 0-10
    for each of the person's picks - how far it was from choosing them.
    """

    person = round_.get("personSelection")
    ai = round_.get("aiSelection") or {}

    if not person or ai.get("status") != "done":
        return None

    shown = list(person.get("shown") or [candidate["url"] for candidate in round_["candidates"]])
    mine = list(person["urls"])
    theirs = [pick["url"] for pick in ai.get("picks") or []]

    # Anything the AI picked outside the list (it cannot: `more` is
    # refused) still counts, at the end.
    over = shown + [url for url in theirs if url not in shown]
    scores = {item["url"]: item.get("score") for item in ai.get("scored") or []}

    both = [url for url in over if url in mine and url in theirs]
    either = [url for url in over if url in mine or url in theirs]

    return {
        "blind": bool(person.get("blind")),
        "over": len(over),
        "person": len(mine),
        "ai": len(theirs),
        "both": both,
        "personOnly": [url for url in over if url in mine and url not in theirs],
        "aiOnly": [url for url in over if url in theirs and url not in mine],
        "precision": _ratio(len(both), len(theirs)),
        "recall": _ratio(len(both), len(mine)),
        "jaccard": _ratio(len(both), len(either)),
        "kappa": kappa(over, set(mine), set(theirs)),
        "aiScores": {url: scores.get(url) for url in mine},
        # For each reason the person gave, how many of their picks it was
        # given for and how many of those the AI chose too.
        "reasons": _reason_tally(person.get("reasons") or {}, set(theirs)),
        # What the person marked not for us, and which of it the AI chose:
        # the starkest disagreement there is.
        "rejected": [url for url in over if url in (round_.get("rejected") or {})],
        "aiPickedRejected": [url for url in theirs if url in (round_.get("rejected") or {})],
        "aiLimit": ai.get("limit"),
        "aiMinScore": ai.get("minScore"),
        "aiModel": ai.get("model"),
        "at": _now(),
    }


def _refuse_rejected(round_: dict, chosen: list[str]) -> None:

    marked = [url for url in chosen if url in (round_.get("rejected") or {})]

    if marked:
        raise InvalidSelection(f"You marked it not for us; undo that first: {marked[0]}")


def _embed(texts: list[str]):
    """inference/'s embeddings, the screen's model (bge-m3); made on first use."""

    from src.services.embeddings.service import EmbeddingService

    return EmbeddingService().encode_many(texts)


def _why(chosen: list[str], notes: dict | None, reasons: dict | None, edition: str) -> dict:
    """The notes and reasons of the chosen urls, cleaned; an unknown reason is refused."""

    try:
        kept_reasons = cleaned_reasons(reasons, chosen, edition)
    except UnknownReason as exc:
        raise InvalidSelection(str(exc))

    return {
        "notes": {
            url: note.strip()[:NOTE_CHARS]
            for url, note in (notes or {}).items()
            if url in chosen and isinstance(note, str) and note.strip()
        },
        "reasons": kept_reasons,
    }


def _reason_tally(reasons: dict[str, list[str]], theirs: set[str]) -> dict[str, dict]:

    tally: dict[str, dict] = {}

    for url, codes in reasons.items():
        for code in codes:
            row = tally.setdefault(code, {"picks": 0, "aiAlso": 0})
            row["picks"] += 1
            row["aiAlso"] += url in theirs

    return tally


def kappa(items: list[str], first: set[str], second: set[str]) -> float | None:
    """
    Cohen's kappa of two raters each marking some of `items` as chosen.
    None when it is undefined: no items, or chance agreement already 1
    (both chose all, or both none).
    """

    if not items:
        return None

    n = len(items)
    agree = sum((item in first) == (item in second) for item in items) / n
    p_first = sum(item in first for item in items) / n
    p_second = sum(item in second for item in items) / n
    chance = p_first * p_second + (1 - p_first) * (1 - p_second)

    if chance >= 1:
        return None

    return round((agree - chance) / (1 - chance), 4)


def _ratio(part: int, whole: int) -> float | None:

    return round(part / whole, 4) if whole else None


def _compared_urls(round_: dict) -> list[str]:
    """The person's picks, then the AI's (when it finished)."""

    person = round_.get("personSelection") or {}
    ai = round_.get("aiSelection") or {}
    theirs = [pick["url"] for pick in ai.get("picks") or []] if ai.get("status") == "done" else []

    return list(person.get("urls") or []) + theirs


def _summary(round_: dict) -> dict:

    ai = round_.get("aiSelection") or {}
    queued = round_.get("queued") or {}
    person = round_.get("personSelection") or {}
    comparison = round_.get("comparison") or {}

    # Rounds from before 2026-10-13 recorded no emphasis.
    emphasis = ((round_.get("ranking") or {}).get("topicEmphasis") or {}).get("applied")

    return {
        "id": round_["id"],
        "startedAt": round_.get("startedAt"),
        "lens": round_.get("lens"),
        "edition": edition_of(round_),
        "groups": round_.get("groups"),
        "topicEmphasis": emphasis,
        "totals": round_.get("totals"),
        "aiStatus": ai.get("status"),
        "aiPicks": len(ai.get("picks") or []),
        "queued": len(queued.get("urls") or []),
        "selectedBy": queued.get("selectedBy"),
        # The person's recorded choice and how much of it the AI shared.
        "personPicks": len(person.get("urls") or []),
        "rejected": len(round_.get("rejected") or {}),
        "personBlind": person.get("blind") if person else None,
        "bothPicked": len(comparison["both"]) if comparison else None,
    }


def edition_of(round_: dict) -> str:
    """A round's edition; rounds from before the editions were all positive."""

    return round_.get("edition") or "positive"


def _now() -> str:

    return datetime.now(timezone.utc).isoformat(timespec="seconds")
