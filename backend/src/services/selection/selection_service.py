"""
The selection step: discovered articles -> up to twenty chosen -> analysis.

POST /ingest sends every new article it finds straight to a full
analysis. A round puts a choice in between:

1. **Candidates** (`create_round`): discovery over the sources of up to
   three topic groups, each article listed with its feed's title and
   summary. Nothing beyond the feeds and section pages is fetched.
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
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from logging import getLogger
from typing import Callable

from src.services.llms import LLMUnavailableError
from src.services.selection.ai_selector import DEFAULT_MIN_SCORE, AISelector
from src.services.selection.rounds import SelectionRounds, selection_rounds as default_rounds

logger = getLogger(__name__)

# The most articles one round sends to analysis. Each is a scrape, an
# enrichment and an LLM call per claim; on the production CPU model one
# article is about three minutes.
MAX_SELECTED = 20

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
    ):
        self.ingestion = ingestion
        self.selector = selector or AISelector()
        self.rounds = rounds if rounds is not None else default_rounds

        self._lock = threading.Lock()
        self._running: str | None = None

    # ------------------------------------------------------------------
    # 1. Candidates
    # ------------------------------------------------------------------

    def create_round(
        self,
        groups: list[str],
        source_ids: list[str] | None = None,
        per_source: int = 3,
    ) -> dict:

        discovered = self.ingestion.discover_candidates(groups, source_ids, per_source)

        round_ = {
            "id": uuid.uuid4().hex[:16],
            **discovered,
            "aiSelection": None,
            "queued": None,
        }

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
    ) -> dict:

        round_ = self.get(round_id)

        if not round_["candidates"]:
            raise InvalidSelection("This round found no candidates to choose from.")

        with self._lock:

            if self._running is not None:
                raise SelectionBusy(self._running)

            self._running = round_id

        round_["aiSelection"] = {
            "status": "running",
            "startedAt": _now(),
            "limit": min(limit, MAX_SELECTED),
            "minScore": min_score,
        }
        self.rounds.save(round_)

        threading.Thread(
            target=self._run_ai_selection,
            args=(round_id, min(limit, MAX_SELECTED), min_score),
            name="ai-selection",
            daemon=True,
        ).start()

        return round_["aiSelection"]

    def run_ai_selection(self, round_id: str, limit: int, min_score: float) -> dict:
        """The selection itself, on the calling thread. The background thread's body; tests call it."""

        round_ = self.get(round_id)
        state = dict(round_.get("aiSelection") or {"startedAt": _now(), "limit": limit, "minScore": min_score})

        try:
            selection = self.selector.select(round_["candidates"], round_["groups"], limit, min_score)
            state.update(status="done", **selection.to_dict())
        except LLMUnavailableError as exc:
            state.update(status="failed", error=f"The LLM could not be reached: {exc}")
        except Exception as exc:
            logger.exception("AI selection failed for round %s", round_id)
            state.update(status="failed", error=str(exc))

        state["finishedAt"] = _now()
        round_["aiSelection"] = state
        self.rounds.save(round_)

        return state

    def _run_ai_selection(self, round_id: str, limit: int, min_score: float) -> None:

        try:
            self.run_ai_selection(round_id, limit, min_score)
        finally:
            with self._lock:
                self._running = None

    # ------------------------------------------------------------------
    # 3. Queue
    # ------------------------------------------------------------------

    def queue(self, round_id: str, urls: list[str], start_job: StartJob) -> dict:

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
        }

        self.rounds.save(round_)

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


def _summary(round_: dict) -> dict:

    ai = round_.get("aiSelection") or {}
    queued = round_.get("queued") or {}

    return {
        "id": round_["id"],
        "startedAt": round_.get("startedAt"),
        "groups": round_.get("groups"),
        "totals": round_.get("totals"),
        "aiStatus": ai.get("status"),
        "aiPicks": len(ai.get("picks") or []),
        "queued": len(queued.get("urls") or []),
        "selectedBy": queued.get("selectedBy"),
    }


def _now() -> str:

    return datetime.now(timezone.utc).isoformat(timespec="seconds")
