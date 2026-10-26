"""
The ranking of a round's candidates: which ones a person sees first, and
so which twenty are shown at all (selection_service.LISTED; forty when
asked for, MAX_LISTED).

A round over two or three topic groups finds 60-80 new articles. The
mission screen leaves out the plainly off-mission ones; what it cannot
separate - housing policy and social stories from the Spanish front
pages, scored among good stories - stayed in a list read top to bottom
in the order the sources are named. Each candidate now gets a score from
four things already at hand when the round is made (no page is fetched,
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

**Positive impact or the topic: the person's call** (`weights`,
2026-10-13). The story's share of the score, STORY_WEIGHT, is split
between its positive-impact reading (news) and its fit with the groups
asked for (topic) by the round's `topic_emphasis`, from 0 (all positive
impact) to 1 (all topic); the source's two parts keep theirs. It is the
person's question - what do I want first, the most positive stories or
the ones most squarely about what I picked - so it comes with the
request, per round, like the groups themselves, and is passed per call:
the services that rank are long-lived singletons. None means
DEFAULT_TOPIC_EMPHASIS. A round with no topic signal - every topic asked
for, or nothing read - has nothing to weigh, and is ranked at
WITHOUT_TOPIC whatever was asked.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.config.topics import GROUP_OF
from src.services.selection.mission_screen import Reading

# How much each part counts. Whatever the emphasis they sum to 1, so a
# score is in [0, 1]: the emphasis moves weight between two parts, it
# never sets one alone - the hazard that keeps the fact-checker's weights
# environment-only (docs/decisions/thresholds.md) cannot arise here.
#
# The source's two parts keep the 2026-10-06 measurement's weights, 0.25
# and 0.15, at every emphasis; the story has the rest, 0.6, which was all
# positive impact then and is now split with the topic. At emphasis 0 the
# score is exactly the 2026-10-06 one, which is also how a round with no
# topic signal is ranked.
SOURCE_WEIGHTS = {"record": 0.25, "reliability": 0.15}

STORY_WEIGHT = 1.0 - sum(SOURCE_WEIGHTS.values())

# The emphasis a round is ranked at when the person asks for none: topic
# 0.36, positive impact 0.24. Measured 2026-10-13 (docs/experiments.md;
# data/evaluation/experiments/emphasis/) by re-scoring every candidate of
# the 2026-10-09 rounds, shown or in reserve and all labelled by hand: over
# the ten one-group rounds of the last two runs, the first twenty held 194
# of 200 stories of the group asked for (184 with the weights before, 174
# at emphasis 0) and the first ten 100 of 100 (94) - the plateau: higher
# gains no more of the group (0.7: 194 and 100) and loses positive stories
# (worth offering of the group 150 at 0.6, 139 at 0.7; 154 before). The
# cost of favouring the topic at all, already paid at 0.5: clearly positive
# stories of the group 62 -> 53, their places taken by squarely on-topic
# hard news - an outbreak in a Health round, AI policy in a Science one.
# Telling those apart is what the AI selection reads the list for.
DEFAULT_TOPIC_EMPHASIS = 0.6

# The emphasis of a round with no topic signal - every topic asked for, or
# inference/ unreachable so nothing was read - whatever was asked: the
# topic's share goes back to the story. Left at the default, 0.36 of every
# score would be the same constant for all and the story would weigh less
# than its source's record.
WITHOUT_TOPIC = 0.0

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


def topic_part(fit: float | None, bounds: tuple[float, float] = TOPIC_RANGE) -> float | None:
    """
    How well the candidate fits the round's groups, in [0, 1]; None when
    no group was asked for or nothing was read. `bounds` other than
    TOPIC_RANGE only for the experiment that tried them.
    """

    if fit is None:
        return None

    return _scaled(fit, bounds)


def record_part(standing: Standing) -> float:
    """The source's part from this round's screen, in [0, 1]."""

    if standing.positive_editorial:
        return 1.0

    return (standing.kept + RECORD_PRIOR * RECORD_STRENGTH) / (standing.judged + RECORD_STRENGTH)


def weights(emphasis: float | None = None) -> dict[str, float]:
    """
    The four weights at a topic emphasis: STORY_WEIGHT split between
    positive impact (`news`, 1 - emphasis of it) and the fit with the
    round's groups (`topic`, emphasis of it), the source's parts as they
    are. None is DEFAULT_TOPIC_EMPHASIS. Raises ValueError outside [0, 1]:
    the API refuses such a value before it gets here.
    """

    emphasis = DEFAULT_TOPIC_EMPHASIS if emphasis is None else emphasis

    if not 0.0 <= emphasis <= 1.0:
        raise ValueError(f"The topic emphasis is between 0 and 1, not {emphasis}.")

    return {
        "news": STORY_WEIGHT * (1.0 - emphasis),
        "topic": STORY_WEIGHT * emphasis,
        **SOURCE_WEIGHTS,
    }


def score(
    news: float | None,
    topic: float | None,
    record: float,
    reliability: float,
    weighted: dict[str, float],
) -> float:
    """
    One candidate's score from its parts under `weighted` (from
    `weights`): `reliability` is the configured rating itself, the others
    in [0, 1]; a part not read counts as UNREAD. The one formula - the
    rounds and the experiment that re-scores them both call it.
    """

    return (
        weighted["news"] * (UNREAD if news is None else news)
        + weighted["topic"] * (UNREAD if topic is None else topic)
        + weighted["record"] * record
        + weighted["reliability"] * _scaled(reliability, RELIABILITY_RANGE)
    )


def rank(
    reading: Reading | None,
    standing: Standing,
    fit: float | None = None,
    emphasis: float | None = None,
) -> dict:
    """
    The score and its parts, as the round records them: `reliability` is
    the configured rating itself, the others in [0, 1]. `fit` is the
    candidate's group_fit for the round's groups (None in a round over
    every topic, where the topic part is the same for all). `emphasis`,
    per call: the round's topic emphasis (None, the default).
    """

    news = news_part(reading)
    topic = topic_part(fit)
    record = record_part(standing)

    return {
        "score": round(score(news, topic, record, standing.reliability, weights(emphasis)), 3),
        "news": None if news is None else round(news, 3),
        "topic": None if topic is None else round(topic, 3),
        "record": round(record, 3),
        "reliability": standing.reliability,
    }


def applied_emphasis(asked: float | None, signal: bool) -> float | None:
    """
    The emphasis a round is ranked at: the one asked for, else the
    default; None when the round has no topic signal (no group asked for,
    or no candidate read), which is then ranked at WITHOUT_TOPIC.
    """

    if not signal:
        return None

    return DEFAULT_TOPIC_EMPHASIS if asked is None else asked


def described(asked: float | None, applied: float | None) -> dict:
    """
    What a round records of how it was ranked, so its order can be
    explained later without the code of the day: the weights its scores
    used, and the emphasis asked for (None: the default), applied (None:
    no topic signal) and the default then.
    """

    used = weights(WITHOUT_TOPIC if applied is None else applied)

    return {
        "weights": {part: round(weight, 4) for part, weight in used.items()},
        "topicEmphasis": {"asked": asked, "applied": applied, "default": DEFAULT_TOPIC_EMPHASIS},
        "sameStory": SAME_STORY,
        "groupFit": GROUP_FIT,
    }


# ----------------------------------------------------------------------
# A trending round (docs/decisions/trends.md, "The lens")
# ----------------------------------------------------------------------
#
# The same score with one part changed. A trend's articles come from
# outlets nobody rated - Spain's ten trends of 2026-10-26 linked 27 domains
# - where reliability is RELIABILITY_RANGE's flat default and says nothing,
# so its 0.15 goes to how much the trend is spreading. The record is the
# signal's in this round's screen, not one outlet's: Google's trends keep
# few, r/UpliftingNews most. Reasoned, not fitted: T6's labelled rounds
# are what will fit them, as 2026-10-06's fitted the sources' weights.
TREND_SOURCE_WEIGHTS = {"record": SOURCE_WEIGHTS["record"], "virality": SOURCE_WEIGHTS["reliability"]}


def trend_weights(emphasis: float | None = None) -> dict[str, float]:
    """
    A trending round's four weights at a topic emphasis: the story's
    STORY_WEIGHT split as in `weights`, the signal's record, and virality
    in reliability's place. They sum to 1 at every emphasis.
    """

    story = weights(emphasis)

    return {"news": story["news"], "topic": story["topic"], **TREND_SOURCE_WEIGHTS}


def trend_rank(
    reading: Reading | None,
    standing: Standing,
    fit: float | None = None,
    virality: float | None = None,
    emphasis: float | None = None,
) -> dict:
    """
    A trend article's score and its parts, as the round records them.
    `standing` is its signal's (record from this round's screen; its
    reliability is not used). `virality` is in [0, 1], None for a trend a
    person typed, which counts as UNREAD.
    """

    news = news_part(reading)
    topic = topic_part(fit)
    record = record_part(standing)
    weighted = trend_weights(emphasis)

    total = (
        weighted["news"] * (UNREAD if news is None else news)
        + weighted["topic"] * (UNREAD if topic is None else topic)
        + weighted["record"] * record
        + weighted["virality"] * (UNREAD if virality is None else virality)
    )

    return {
        "score": round(total, 3),
        "news": None if news is None else round(news, 3),
        "topic": None if topic is None else round(topic, 3),
        "record": round(record, 3),
        "virality": None if virality is None else round(virality, 3),
    }


def described_trending(asked: float | None, applied: float | None) -> dict:
    """`described`, for a trending round: its own weights, and the lens it was ranked under."""

    used = trend_weights(WITHOUT_TOPIC if applied is None else applied)

    return {
        "lens": "trending",
        "weights": {part: round(weight, 4) for part, weight in used.items()},
        "topicEmphasis": {"asked": asked, "applied": applied, "default": DEFAULT_TOPIC_EMPHASIS},
        "sameStory": SAME_STORY,
        "groupFit": GROUP_FIT,
    }


def best_first(candidates: list[dict]) -> list[dict]:
    """By score; candidates scored alike keep their order."""

    return sorted(candidates, key=lambda candidate: candidate["rank"]["score"], reverse=True)


def ordered(
    candidates: list[dict],
    fits: dict[str, float],
    nearest: dict[str, str],
    vectors: dict[str, np.ndarray],
) -> list[dict]:
    """
    A round's order: best first, those nearer another group after the
    rest (`fitting_first`), each story once before any twice
    (`one_per_story`). Marks the candidates it moves.
    """

    return one_per_story(fitting_first(best_first(candidates), fits, nearest), vectors)


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
