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
4. **Topic** (added 2026-10-09) - how well it fits the groups the round
   asked for: its `group_fit`, scaled. Within GROUP_FIT a story of
   another group was ranked on its own merits alone - the T. rex, a
   tortoise's longevity and a hospital dog among an Environment round's
   first twenty.

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

**The groups asked for, first** (`fitting_first`). A source names every
group it has sections for, and its feed is read for all of them: on
2026-10-09 a Health round listed the chemistry Nobel and a Japanese
headband's symbolism, Environment and Culture both listed Positive News's
breakfast advice, and Society an MIT sensor sheet and Meta's business.
A candidate whose nearest topic in the round's groups is further than
GROUP_FIT behind its nearest topic elsewhere is marked `otherGroup` (the
group of that nearest topic) and goes after every candidate that fits -
moved, like a repeat, never dropped: a story can belong to two groups.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.config.topics import GROUP_OF
from src.services.selection.mission_screen import Reading

# How much each part counts. They sum to 1, so a score is in [0, 1].
#
# The topic part's 0.15, the other three keeping their proportions, was
# measured on 2026-10-09 (docs/experiments.md) over ten labelled one-group
# rounds: among their first twenty, stories of another group went from 26
# to 15 and stories worth offering of the round's own group stayed at 150
# (clearly positive ones 61 -> 60). At 0.25 the other-group ones fell to 9
# but 5 worth offering of the round's own group went with them, and at
# 0.35 to 6 for 9. The three older parts' weights, 0.6 / 0.25 / 0.15, are
# the 2026-10-06 measurement's.
WEIGHTS = {"news": 0.51, "topic": 0.15, "record": 0.21, "reliability": 0.13}

# group_fit scaled to [0, 1] between these: GROUP_FIT, where a candidate
# starts to be listed after the rest, and the fit of a story squarely on
# the round's topics (an Environment round's rhino translocation 0.04, its
# compost-everything story 0.09).
TOPIC_RANGE = (-0.05, 0.10)

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

# How far a candidate's nearest topic in the round's groups may trail its
# nearest topic in any other before it is listed after those that fit.
# Measured 2026-10-09 (docs/experiments.md; data/evaluation/experiments/
# alignment/): over 149 articles of that day's five one-group rounds,
# labelled by hand with the groups each story belongs to, the fit told a
# story of the round's group from one of another's with AUC 0.874 [0.81,
# 0.93]. At -0.05 it moves 18 of the 34 that belonged elsewhere and 10 of
# the 115 that belonged - 4 of those clearly positive, and each of the 10
# a story whose first group is another (a testicular-tissue transplant in
# a Science round).
GROUP_FIT = -0.05


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


def topic_part(fit: float | None) -> float | None:
    """How well the candidate fits the round's groups, in [0, 1]; None when no group was asked for or nothing was read."""

    if fit is None:
        return None

    return _scaled(fit, TOPIC_RANGE)


def record_part(standing: Standing) -> float:
    """The source's part from this round's screen, in [0, 1]."""

    if standing.positive_editorial:
        return 1.0

    return (standing.kept + RECORD_PRIOR * RECORD_STRENGTH) / (standing.judged + RECORD_STRENGTH)


def rank(reading: Reading | None, standing: Standing, fit: float | None = None) -> dict:
    """
    The score and its parts, as the round records them: `reliability` is
    the configured rating itself, the others in [0, 1]. `fit` is the
    candidate's group_fit for the round's groups (None in a round over
    every topic, where the topic part is the same for all).
    """

    news = news_part(reading)
    topic = topic_part(fit)
    record = record_part(standing)

    score = (
        WEIGHTS["news"] * (UNREAD if news is None else news)
        + WEIGHTS["topic"] * (UNREAD if topic is None else topic)
        + WEIGHTS["record"] * record
        + WEIGHTS["reliability"] * _scaled(standing.reliability, RELIABILITY_RANGE)
    )

    return {
        "score": round(score, 3),
        "news": None if news is None else round(news, 3),
        "topic": None if topic is None else round(topic, 3),
        "record": round(record, 3),
        "reliability": standing.reliability,
    }


def best_first(candidates: list[dict]) -> list[dict]:
    """By score; candidates scored alike keep their order."""

    return sorted(candidates, key=lambda candidate: candidate["rank"]["score"], reverse=True)


def group_fit(reading: Reading | None, topics: list[str]) -> float | None:
    """
    How much nearer the candidate comes to the nearest of `topics` (the
    round's groups') than to the nearest other topic: positive when it
    fits, negative when another group's topic is nearer. None when
    nothing was read, or every topic was asked for.
    """

    if reading is None or not reading.topics:
        return None

    inside = [similarity for topic, similarity in reading.topics.items() if topic in topics]
    outside = [similarity for topic, similarity in reading.topics.items() if topic not in topics]

    if not inside or not outside:
        return None

    return max(inside) - max(outside)


def fitting_first(candidates: list[dict], fits: dict[str, float], nearest: dict[str, str]) -> list[dict]:
    """
    `candidates` (best first) with those whose fit (`fits`, by url) is
    below GROUP_FIT moved after the rest, each part in its order, and
    marked `otherGroup`: the group of their nearest topic (`nearest`). A
    candidate without a fit stays where it is.
    """

    fitting, others = [], []

    for candidate in candidates:

        fit = fits.get(candidate["url"])

        if fit is not None and fit < GROUP_FIT:
            candidate["otherGroup"] = GROUP_OF.get(nearest.get(candidate["url"]))
            others.append(candidate)
        else:
            fitting.append(candidate)

    return fitting + others


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
