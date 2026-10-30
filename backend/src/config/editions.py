"""
The two editions the newsroom can run: `positive` (Inspiring News, as it
always was) and `devastating` (the news that is bad for humanity, told by
a self-important narrator). docs/decisions/editions.md.

An edition is chosen per run, like a threshold, and travels the same way:
`PipelineThresholds.edition` for an analysis, a round's `edition` for
discovery and selection, a draft's `edition` for writing. Never a
setting: the components are process singletons shared by every request,
and one person's Devastating round must not turn another's Positive one.

What it changes, and only this:

- the topic labels (TOPICS or DEVASTATING_TOPICS) and their five groups;
- admission's tone gate (positive impact, or devastation);
- the mission screen's idea of on and off mission, and so the ranking;
- the AI selection's question;
- the trend signals read;
- the writer's voice;
- whether the fact-check runs: the Devastating edition is not
  fact-checked since 2026-10-30, at the request of the person running it
  (AnalysisService._check); its stories rest on their outlets' reporting,
  are written only from what those articles say, and are shown as "Not
  checked".
"""

from __future__ import annotations

from typing import Literal

from src.config.topics import (
    DEVASTATING_GROUP_OF,
    DEVASTATING_TOPIC_GROUP_NAMES,
    DEVASTATING_TOPIC_GROUPS,
    DEVASTATING_TOPIC_KEYWORDS_ES,
    DEVASTATING_TOPICS,
    GROUP_OF,
    TOPIC_GROUP_NAMES,
    TOPIC_GROUPS,
    TOPIC_KEYWORDS_ES,
    TOPICS,
)
from src.models.nlp.topics import Topic

Edition = Literal["positive", "devastating"]

EDITIONS: tuple[str, ...] = ("positive", "devastating")

DEFAULT_EDITION: Edition = "positive"

EDITION_NAMES = {
    "positive": "Inspiring News",
    "devastating": "Devastating News",
}


def known_edition(edition: str | None) -> Edition:
    """`edition`, or the default for None; anything else is refused."""

    if edition is None:
        return DEFAULT_EDITION

    if edition not in EDITIONS:
        raise ValueError(f"Unknown edition {edition!r}; expected one of {', '.join(EDITIONS)}.")

    return edition  # type: ignore[return-value]


def topics_of(edition: str | None = None) -> dict[str, Topic]:

    return DEVASTATING_TOPICS if known_edition(edition) == "devastating" else TOPICS


def groups_of(edition: str | None = None) -> dict[str, list[str]]:

    return DEVASTATING_TOPIC_GROUPS if known_edition(edition) == "devastating" else TOPIC_GROUPS


def group_names_of(edition: str | None = None) -> dict[str, str]:

    return DEVASTATING_TOPIC_GROUP_NAMES if known_edition(edition) == "devastating" else TOPIC_GROUP_NAMES


def edition_of_topic(topic_id: str) -> Edition | None:

    if topic_id in TOPICS:
        return "positive"

    if topic_id in DEVASTATING_TOPICS:
        return "devastating"

    return None


# Either edition's topic, by id - the ids are distinct, which a test holds.
# For code that is handed topic ids and only needs their keywords or
# group: discovery's feed filter, the ranking's "of another group".
ALL_TOPICS: dict[str, Topic] = {**TOPICS, **DEVASTATING_TOPICS}

ALL_GROUP_OF: dict[str, str] = {**GROUP_OF, **DEVASTATING_GROUP_OF}

ALL_TOPIC_KEYWORDS_ES: dict[str, list[str]] = {**TOPIC_KEYWORDS_ES, **DEVASTATING_TOPIC_KEYWORDS_ES}
