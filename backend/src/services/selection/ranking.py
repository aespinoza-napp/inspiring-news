"""
The ranking of a round's candidates: which ones a person sees first, and
so which twenty are shown at all (selection_service.LISTED; forty when
asked for, MAX_LISTED).

A round over two or three topic groups finds 60-80 new articles. The
mission screen leaves out the plainly off-mission ones; what it cannot
separate - housing policy and social stories from the Spanish front
pages, scored among good stories - stayed in a list read top to bottom
in the order the sources are named. Each candidate now gets a score from
three things already at hand when the round is made (no page is fetched,
no LLM is asked):

1. **News** - what its own title and summary say: how much nearer they
   are to a description of positive impact (mission_screen.IMPACT) than
   to the nearest off-mission description. The screen's embedding pass,
   one more label.
2. **Source record** - how much of what its source offered this round
   was on-mission: the share of the source's newest items the screen kept
   (`judged` of them read, `kept` kept), smoothed towards RECORD_PRIOR so
   that five items say little. Outlets with `positive_editorial` count as
   1: their editors chose, and they are not screened.
3. **Reliability** - the source's configured `reliability_index`, the
   rating its pages get as evidence in the fact-check.

Measured on 2026-10-06 (docs/experiments.md; the labelled set and every
reading in data/evaluation/experiments/ranking/) against 117 candidates
of the five rounds recorded that day, each read and labelled by hand.
Over the 86 the screen keeps, as the probability that a story worth
offering outranks one that is not (AUC): news 0.75, and 0.81 for the
clearly positive ones; news and record together 0.79 and 0.82; the
app's own AI selection (llama3.2:3b) 0.65 and 0.75. On the rounds
themselves the first twenty of a Science and Society round held 8
stories not worth offering in the sources' order and 1 ranked, and 14
clearly positive ones instead of 6.

The reliability rating does not tell a positive story from another
(AUC 0.49 - Good News Network is rated 0.65, a general outlet's election
coverage 0.9). It is in because how far a source is trusted is part of
what the publication offers, and it has the smallest say: with it, 0.78
and 0.81 instead of 0.79 and 0.82, well inside the intervals of 86
stories (about +-0.1).

Left out: freshness. Inside MAX_CANDIDATE_AGE, newer ranked worse (AUC
0.30): the day's breaking news is mostly the day's politics.

**One story, once** (`one_per_story`). Run live on the new code, the
same Science and Society round put the physics Nobel in 8 of its first
twenty places - nine outlets, two languages, each scored high on its own.
A candidate whose embedding is within SAME_STORY of one already placed is
marked `sameStoryAs` that story's best-ranked candidate and goes after
every distinct story; nothing is dropped.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.services.selection.mission_screen import Reading

# How much each part counts. They sum to 1, so a score is in [0, 1].
WEIGHTS = {"news": 0.6, "record": 0.25, "reliability": 0.15}

# impact minus nearest off-mission, scaled to [0, 1] between these: the
# 5th and 95th percentiles over the 86 measured candidates the screen
# kept (-0.107 and 0.077). Beyond them a candidate scores 0 or 1.
NEWS_RANGE = (-0.11, 0.08)

# The configured ratings run from 0.65 (Good News Network) to 1.0 (NASA,
# ESA).
RELIABILITY_RANGE = (0.6, 1.0)

# A source's record before this round says anything: the share the screen
# kept over the three screened rounds of 2026-10-06 (0.81), worth this
# many items. A source with 15 read and 15 kept scores 0.95; 8 of 15, 0.6.
RECORD_PRIOR = 0.8
RECORD_STRENGTH = 5

# A candidate with nothing read - no text, or inference/ unreachable -
# counts as the median of the measured ones (0.47) rather than as bad or
# good: the source parts order it.
UNREAD = 0.5

# Two candidates this near (cosine of their title-and-summary embeddings)
# report the same story. In that live round the physics Nobel's nine
# versions paired at 0.68-0.88, and each was within 0.75 of another; the
# nearest two different stories came to 0.69 (two Nature editorials; two
# Muy Interesante pieces on ancient viruses in our genome).
SAME_STORY = 0.75


@dataclass(frozen=True)
class Standing:
    """What a round knows of one source."""

    reliability: float

    positive_editorial: bool = False

    # This round: how many of the source's newest items the screen read,
    # and how many of those it kept.
    judged: int = 0

    kept: int = 0


def news_part(reading: Reading | None) -> float | None:
    """The candidate's own part, in [0, 1]; None when nothing was read."""

    if reading is None:
        return None

    return _scaled(reading.impact - reading.off, NEWS_RANGE)


def record_part(standing: Standing) -> float:
    """The source's part from this round's screen, in [0, 1]."""

    if standing.positive_editorial:
        return 1.0

    return (standing.kept + RECORD_PRIOR * RECORD_STRENGTH) / (standing.judged + RECORD_STRENGTH)


def rank(reading: Reading | None, standing: Standing) -> dict:
    """
    The score and its parts, as the round records them: `reliability` is
    the configured rating itself, the others in [0, 1].
    """

    news = news_part(reading)
    record = record_part(standing)

    score = (
        WEIGHTS["news"] * (UNREAD if news is None else news)
        + WEIGHTS["record"] * record
        + WEIGHTS["reliability"] * _scaled(standing.reliability, RELIABILITY_RANGE)
    )

    return {
        "score": round(score, 3),
        "news": None if news is None else round(news, 3),
        "record": round(record, 3),
        "reliability": standing.reliability,
    }


def best_first(candidates: list[dict]) -> list[dict]:
    """By score; candidates scored alike keep their order."""

    return sorted(candidates, key=lambda candidate: candidate["rank"]["score"], reverse=True)


def one_per_story(candidates: list[dict], vectors: dict[str, np.ndarray]) -> list[dict]:
    """
    `candidates` (best first) with every story once before any story
    twice. A candidate within SAME_STORY of any of a story's candidates
    already placed joins that story: it is marked `sameStoryAs` the
    story's first (best-ranked) url and moved after every distinct one,
    the repeats still best first among themselves. A candidate without a
    vector is a story of its own.
    """

    stories: list[tuple[str, list[np.ndarray]]] = []
    distinct: list[dict] = []
    repeats: list[dict] = []

    for candidate in candidates:

        vector = vectors.get(candidate["url"])
        story = None

        if vector is not None:
            story = next(
                (
                    (lead, members) for lead, members in stories
                    if any(float(vector @ member) >= SAME_STORY for member in members)
                ),
                None,
            )

        if story is None:
            distinct.append(candidate)
            if vector is not None:
                stories.append((candidate["url"], [vector]))
        else:
            lead, members = story
            members.append(vector)
            candidate["sameStoryAs"] = lead
            repeats.append(candidate)

    return distinct + repeats


def _scaled(value: float, bounds: tuple[float, float]) -> float:

    low, high = bounds

    return min(1.0, max(0.0, (value - low) / (high - low)))
