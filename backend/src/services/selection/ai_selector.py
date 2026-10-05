"""
The AI half of the selection step: an LLM scores each candidate's
positive impact from its title and feed summary, before any page is
fetched.

Why an LLM here and not the admission filter's positive-impact score:
that score counts upbeat words. Measured on 2026-10-05's ten articles,
it ranked a football match report (0.34) and an arson story (0.43) above
an analysis of Chinese industry leaving fossil fuels (0.28). What the
publication means by positive impact is a judgement about what changed
and for whom, which is what DEFINITION asks the model for.

Why it costs little: one call per BATCH candidates, not one per article,
over a title and a few sentences each. A candidate it picks still goes
through the whole pipeline - admission included - so this ranks what to
spend analyses on; it does not replace any check.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from logging import getLogger

from src.config.settings import settings
from src.config.topics import TOPIC_GROUP_NAMES
from src.services.concurrency import bounded_map
from src.services.llms import LLMClient

logger = getLogger(__name__)

# Candidates per LLM call. A small local model loses track of a long
# numbered list - it skips items or scores the wrong number - so the list
# is cut into short ones, each answered on its own. Short enough that one
# answer fits AI_SELECTION_TIMEOUT on a CPU: 13 took 72s on a GPU.
BATCH = 10

# Scores are 0-10; a pick needs at least this many unless the caller
# asks otherwise. 6 is "clearly a positive-impact story", reasoned, not
# fitted: the selection rounds record every score, so it can be fitted
# against the editor's own picks later.
DEFAULT_MIN_SCORE = 6.0

SUMMARY_CHARS = 300

REASON_CHARS = 200

DEFINITION = """\
You choose stories for Inspiring News, a publication of positive-impact journalism.

Score each article from 0 to 10 for positive impact. High: it reports a real change that \
improves things for people or the planet beyond the people in the story - progress, a \
solution that works, a recovery, a discovery with a use - backed by something checkable \
(a study, data, an official source). Low: sports results, celebrity and lifestyle \
interviews, entertainment, personal advice, opinion, crime, conflict and disasters \
(however well written), and anything outside the chosen topics.

Judge only from the title and summary given; do not assume what they do not say. \
Write each reason in English, in at most twelve words, whatever the article's language."""

ANSWER_FORMAT = """\
Reply with JSON only, one entry per article, using its number:
{"scores": [{"i": 1, "score": 7, "reason": "..."}]}"""


@dataclass
class Scored:

    url: str

    # None when the model was asked and left this candidate out.
    score: float | None

    reason: str | None = None


@dataclass
class AISelection:

    picks: list[Scored]

    scored: list[Scored]

    model: str

    calls: int

    # Batches whose answer had no usable JSON: their candidates are unscored.
    unusable: int = 0

    elapsed_ms: int = 0

    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:

        def row(item: Scored) -> dict:
            return {"url": item.url, "score": item.score, "reason": item.reason}

        return {
            "picks": [row(item) for item in self.picks],
            "scored": [row(item) for item in self.scored],
            "model": self.model,
            "calls": self.calls,
            "unusable": self.unusable,
            "elapsedMs": self.elapsed_ms,
            "notes": self.notes,
        }


class AISelector:

    def __init__(self, llm: LLMClient | None = None):

        # Built on first use, not here: the container constructs the
        # selection service for routes that never call the model.
        self._llm = llm

    @property
    def llm(self) -> LLMClient:

        if self._llm is None:
            self._llm = LLMClient(timeout=settings.AI_SELECTION_TIMEOUT)

        return self._llm

    def select(
        self,
        candidates: list[dict],
        groups: list[str],
        limit: int,
        min_score: float = DEFAULT_MIN_SCORE,
    ) -> AISelection:
        """
        Every candidate scored, and the best `limit` of those reaching
        `min_score` picked. Raises LLMUnavailableError when the model
        could not be reached for any batch: a selection made from part of
        the list would look like a judgement on all of it.
        """

        started = time.perf_counter()

        batches = [candidates[i:i + BATCH] for i in range(0, len(candidates), BATCH)]

        # Input order is kept (bounded_map), so batch k's answer is
        # matched to batch k's candidates. The LLM permit inside
        # complete_json is what bounds how many calls run at once.
        answers = bounded_map(
            lambda batch: self._score_batch(batch, groups),
            batches,
            max_workers=max(len(batches), 1),
            thread_name_prefix="ai-selection",
        )

        scored: list[Scored] = []
        unusable = 0

        for batch, answer in zip(batches, answers):

            if answer is None:
                unusable += 1

            scored.extend(_match(batch, answer))

        ranked = sorted(
            (item for item in scored if item.score is not None and item.score >= min_score),
            key=lambda item: item.score,
            reverse=True,
        )

        notes = []

        if unusable:
            notes.append(f"{unusable} of {len(batches)} answers had no usable JSON; their candidates are unscored.")

        missing = sum(1 for item in scored if item.score is None)

        if missing:
            notes.append(f"{missing} candidates were not scored.")

        return AISelection(
            picks=ranked[:limit],
            scored=scored,
            model=self.llm.model,
            calls=len(batches),
            unusable=unusable,
            elapsed_ms=round((time.perf_counter() - started) * 1000),
            notes=notes,
        )

    def _score_batch(self, batch: list[dict], groups: list[str]) -> dict | None:

        return self.llm.complete_json(DEFINITION + "\n\n" + ANSWER_FORMAT, prompt(batch, groups))


def prompt(batch: list[dict], groups: list[str]) -> str:
    """The numbered list the model scores: number, language, title, source, summary."""

    topics = ", ".join(TOPIC_GROUP_NAMES.get(group, group) for group in groups) or "any"

    lines = [f"Chosen topics: {topics}.", ""]

    for number, candidate in enumerate(batch, start=1):

        title = candidate.get("title") or candidate.get("url")
        lines.append(f"{number}. [{candidate.get('language') or '?'}] {title} ({candidate.get('sourceName') or candidate.get('source')})")

        summary = (candidate.get("summary") or "").strip()

        if summary:
            lines.append(f"   {summary[:SUMMARY_CHARS]}")

    return "\n".join(lines)


def _match(batch: list[dict], answer: dict | None) -> list[Scored]:
    """
    The model's scores matched to the batch by number. Anything it got
    wrong - a number outside the list, a score that is not a number, an
    item scored twice - is left unscored rather than guessed: an
    unscored candidate is not picked, a misattributed one would be.
    """

    by_number: dict[int, tuple[float, str | None]] = {}
    seen_twice: set[int] = set()

    entries = (answer or {}).get("scores")

    for entry in entries if isinstance(entries, list) else []:

        if not isinstance(entry, dict):
            continue

        number = entry.get("i")
        score = entry.get("score")

        if isinstance(number, bool) or not isinstance(number, int) or not 1 <= number <= len(batch):
            continue

        if isinstance(score, bool) or not isinstance(score, (int, float)):
            continue

        if number in by_number:
            seen_twice.add(number)
            continue

        reason = entry.get("reason")
        reason = str(reason).strip()[:REASON_CHARS] if reason else None

        by_number[number] = (max(0.0, min(float(score), 10.0)), reason)

    scored = []

    for number, candidate in enumerate(batch, start=1):

        if number in by_number and number not in seen_twice:
            score, reason = by_number[number]
            scored.append(Scored(candidate["url"], score, reason))
        else:
            scored.append(Scored(candidate["url"], None))

    return scored
