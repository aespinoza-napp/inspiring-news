"""
"For you" (docs/goals.md, N7): the published stories that fit what a
reader follows, each with the parts of its score and why it is there.

Stateless: the reader's interests, saved and hidden stories and their
"not interested" factors come in with the request (from their account,
or from their browser when signed out), and nothing is stored here.

Every story is scored in parts, each in [0, 1] (src/config/for_you.py):
a followed topic or group, followed names, nearness in meaning to the
saved stories, freshness. The score is the parts weighted by the
reader's weights, which sum to 1, so what is shown adds up to it. Then
two rules of variety, in this order: within the first ten, at most 7
from a topic the reader follows and 3 from any other; and of two stories
from one outlet within an hour, only the better one. A saved or hidden
story is never offered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np

from src.config import for_you as config
from src.config.topics import GROUP_OF, TOPIC_GROUP_NAMES
from src.services.news_map.days import today as madrid_today
from src.services.news_map.layout import anchors

PARTS = tuple(config.FOR_YOU_WEIGHTS)


@dataclass
class ReaderProfile:
    groups: set[str] = field(default_factory=set)
    topics: set[str] = field(default_factory=set)
    entities: set[str] = field(default_factory=set)
    saved: set[str] = field(default_factory=set)
    hidden: set[str] = field(default_factory=set)
    # Per part, in [NOT_INTERESTED_FLOOR, 1]: 1 unless "not interested" lowered it.
    factors: dict[str, float] = field(default_factory=dict)

    @classmethod
    def of(cls, interests: list[dict], saved=(), hidden=(), factors=None) -> "ReaderProfile":

        profile = cls(saved=set(saved), hidden=set(hidden), factors=dict(factors or {}))

        for item in interests:
            kind, key = item.get("kind"), item.get("key")
            if kind == "group":
                profile.groups.add(key)
            elif kind == "topic":
                profile.topics.add(key)
            elif kind == "entity":
                profile.entities.add(key)

        return profile

    @property
    def empty(self) -> bool:
        return not (self.groups or self.topics or self.entities or self.saved)


def reader_weights(factors: dict[str, float]) -> dict[str, float]:
    """The base weights scaled by the reader's factors, summing to 1 again."""

    scaled = {
        part: weight * min(1.0, max(config.NOT_INTERESTED_FLOOR, float(factors.get(part, 1.0))))
        for part, weight in config.FOR_YOU_WEIGHTS.items()
    }
    total = sum(scaled.values())

    return {part: value / total for part, value in scaled.items()}


def lowered(factors: dict[str, float], part: str) -> dict[str, float]:
    """The factors after one "not interested" because of `part`."""

    if part not in PARTS:
        return dict(factors)

    current = float(factors.get(part, 1.0))

    return {**factors, part: max(config.NOT_INTERESTED_FLOOR, current * config.NOT_INTERESTED_STEP)}


def _age_days(day: str | None, today: date) -> float | None:

    if not day:
        return None

    try:
        return max(0.0, (today - date.fromisoformat(day)).days)
    except ValueError:
        return None


def rank(context, profile: ReaderProfile, limit: int = 20, today: date | None = None) -> dict:
    """
    `context` is a news_map.search.SearchContext: the published stories,
    the names with their stories, and the unit vectors.
    """

    today = today or madrid_today()
    weights = reader_weights(profile.factors)
    names = {entity.key: (entity.name, len(ids)) for entity, ids in context.entity_rows}
    topic_names = {key: a.name for key, a in anchors().items()}

    # Nearness: the saved stories' mean direction.
    centre = None
    if profile.saved and context.matrix is not None:
        rows = [i for i, article_id in enumerate(context.matrix_ids) if article_id in profile.saved]
        if rows:
            mean = context.matrix[rows].mean(axis=0)
            norm = float(np.linalg.norm(mean))
            centre = mean / norm if norm else None

    nearness = {}
    if centre is not None:
        cosines = context.matrix @ centre
        span = config.NEARNESS_FULL - config.NEARNESS_FROM
        for article_id, cosine in zip(context.matrix_ids, cosines):
            nearness[article_id] = float(min(1.0, max(0.0, (cosine - config.NEARNESS_FROM) / span)))

    scored = []

    for article in context.articles:

        if article.id in profile.saved or article.id in profile.hidden:
            continue

        reasons = []

        topic = 0.0
        for key, confidence in article.topics:
            if key in profile.topics:
                value = min(1.0, confidence / config.TOPIC_FULL_CONFIDENCE)
                if value > topic:
                    topic = value
                reasons.append(f"you follow {topic_names.get(key, key)}")
        if topic == 0.0 and article.group in profile.groups:
            topic = config.GROUP_SHARE
            reasons.append(f"in {TOPIC_GROUP_NAMES.get(article.group, article.group)}, which you follow")

        entity = 0.0
        for e in article.entities:
            if e.key in profile.entities:
                entity += 2.0 / max(1, names.get(e.key, (e.name, 1))[1])
                reasons.append(f"you follow {e.name}")
        entity = min(1.0, entity)

        near = nearness.get(article.id, 0.0)
        if near > 0:
            reasons.append("close to stories you saved")

        age = _age_days(article.day, today)
        fresh = 0.5 ** (age / config.FRESHNESS_HALF_LIFE_DAYS) if age is not None else 0.0

        parts = {"topic": topic, "entity": entity, "nearness": near, "freshness": fresh}
        shown = {part: round(weights[part] * parts[part], 4) for part in PARTS}

        scored.append((round(sum(shown.values()), 4), article, shown, list(dict.fromkeys(reasons))))

    scored.sort(key=lambda row: (-row[0], -row[1].sort_at, row[1].id))

    chosen = _varied(scored, profile, limit)

    return {
        "weights": {part: round(w, 4) for part, w in weights.items()},
        "baseWeights": dict(config.FOR_YOU_WEIGHTS),
        "coldStart": profile.empty,
        "considered": len(scored),
        "items": [
            {
                "id": article.id,
                "title": article.title,
                "source": article.source,
                "day": article.day,
                "verdict": article.verdict,
                "x": round(article.x, 4),
                "y": round(article.y, 4),
                "score": score,
                "parts": shown,
                # The part that counts most: what "not interested" lowers.
                "mainPart": max(shown, key=lambda part: shown[part]),
                "reasons": reasons or (["new"] if shown["freshness"] > 0 else []),
            }
            for score, article, shown, reasons in chosen
        ],
    }


def _main_topic(article) -> str | None:
    return article.topics[0][0] if article.topics else None


def _varied(scored: list, profile: ReaderProfile, limit: int) -> list:
    """
    The rules of variety, greedily down the ranked list. What the topic
    caps hold back out of the first ten comes straight after them, best
    first; the outlet rule holds throughout.
    """

    chosen: list = []
    per_topic: dict[str, int] = {}
    by_outlet: dict[str, list[float]] = {}
    held: list = []

    def crowded(article) -> bool:
        return any(abs(article.sort_at - other) < config.SAME_OUTLET_SECONDS for other in by_outlet.get(article.source, []))

    def take(row) -> None:
        article = row[1]
        chosen.append(row)
        by_outlet.setdefault(article.source, []).append(article.sort_at)
        topic = _main_topic(article)
        if len(chosen) <= config.DIVERSITY_WINDOW and topic is not None:
            per_topic[topic] = per_topic.get(topic, 0) + 1

    def release() -> None:
        while held and len(chosen) < limit:
            row = held.pop(0)
            if not crowded(row[1]):
                take(row)

    for row in scored:

        if len(chosen) >= limit:
            break

        article = row[1]

        if crowded(article):
            continue

        topic = _main_topic(article)

        if len(chosen) < config.DIVERSITY_WINDOW and topic is not None:
            followed = topic in profile.topics or GROUP_OF.get(topic) in profile.groups
            cap = config.MAX_FROM_A_FOLLOWED_TOPIC if followed else config.MAX_FROM_ANOTHER_TOPIC
            if per_topic.get(topic, 0) >= cap:
                held.append(row)
                continue

        take(row)

        if len(chosen) == config.DIVERSITY_WINDOW:
            release()

    release()

    return chosen
