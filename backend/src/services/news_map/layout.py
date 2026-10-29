"""
Where an article sits on the news map.

The map is a disc. The five topic groups are sectors of it, in
TOPIC_GROUPS' order, clockwise from the top; each of the 23 topics is an
anchor inside its group's sector, in src/config/topics.py's order. An
article sits at its main topic's anchor, pulled towards its other
topics' anchors as far as they tie the main one, plus a small offset
from its own embedding, so similar stories gather within a topic.

Not the confidence-weighted mean of its topics' anchors, which the goal
first said (docs/goals.md, N1). The classifier's confidences are
compressed: the first article read on 29 Oct had Entertainment 0.373,
Sustainability 0.360 and Cities & Society 0.350, three topics in three
groups, and a mean of their anchors would put it, and nearly everything,
near the centre - no sections. So the main topic decides the place and
a second topic counts only when it ties it (TIE_MARGIN).

**Positions are stable.** Everything here is a function of one article
and LAYOUT_VERSION: no corpus statistic, no fit. A new article never
moves an old one. The embedding offset is a projection on a fixed random
basis seeded by the version, not a PCA of the corpus, which would move
every point each time it was refitted and needs a corpus the lake does
not yet have (2 publishable articles on 29 Oct). Changing any constant
below changes the map, so it changes LAYOUT_VERSION too.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from src.config.topics import GROUP_OF, TOPIC_GROUP_NAMES, TOPIC_GROUPS, TOPICS

LAYOUT_VERSION = 1

# The circle is cut into one slot per topic, plus GROUP_GAP slots of
# empty space after each group, so the sections read as sections. A
# group's sector is its topics' slots: 4 or 5 of them.
GROUP_GAP = 0.6
SLOT = 2 * math.pi / (len(TOPICS) + GROUP_GAP * len(TOPIC_GROUPS))

# Topic anchors alternate between two radii around the whole circle, not
# within each group: alternating per group put the edge anchors of two
# neighbouring groups on the same ring, 0.18 apart (food and arts). With
# 23 topics one pair must share a ring; the alternation starts on the
# outer one, so that pair is two outer anchors across a group's gap.
# The radii and GROUP_GAP were searched for the widest closest pair of
# anchors with a gap still visible: 0.287 apart (0.239 at 0.50 / 0.82),
# over the 0.24 two full clusters need (a test).
INNER_RADIUS = 0.60
OUTER_RADIUS = 0.88

# How far an article's own embedding moves it from where its topics put
# it: the radius of a topic's cluster.
CLUSTER_RADIUS = 0.075

# A second topic within TIE_MARGIN confidence of the main one pulls the
# article towards its anchor, by up to MAX_PULL when tied; all pulls
# together by at most MAX_PULL. A distance, not a share of the way: the
# other anchor may be across the disc, and a share of that carried the
# first article read (three near-tied topics in three groups) past a
# neighbouring anchor. With CLUSTER_RADIUS it stays under half the
# closest two anchors' distance, so the main topic is always the nearest.
TIE_MARGIN = 0.05
MAX_PULL = 0.045

# How the projected embedding is squashed into the cluster: tanh(|z| /
# SPREAD) of the radius. Measured on 29 Oct on the 139 hand-labelled
# claims embedded by bge-m3: |z| has a median of 0.98 and a p90 of 1.67,
# and within one topic a spread of 0.47-0.83. The first squash, r * z /
# sqrt(1 + |z|^2), put half of every cluster in its outer 30% - rings,
# and crescents where a topic leans one way (seen at 3,000 articles). At
# SPREAD 2 the median point sits at 0.46 of the radius.
SPREAD = 2.0

# Where an article no topic places goes: a ring just outside the disc,
# beyond the outer clusters' reach (0.88 + 0.075 + 0.045).
RIM_RADIUS = 1.08

# The basis the embedding is projected on: fixed by the version.
BASIS_SEED = 20261029 + LAYOUT_VERSION

GROUP_ORDER: tuple[str, ...] = tuple(TOPIC_GROUPS)

# The classifier and the lake name topics by their display name
# ("Cities & Society"); the map and the graph by key ("cities").
_KEY_OF_NAME = {topic.name.casefold(): key for key, topic in TOPICS.items()}


@dataclass(frozen=True)
class Anchor:
    key: str
    name: str
    group: str
    x: float
    y: float


@dataclass(frozen=True)
class Placement:
    x: float
    y: float
    # The group and topics that placed it, main topic first.
    group: str | None
    topics: tuple[str, ...]
    # Why it is not where its own text would put it: "no_vector" (topics
    # only, a deterministic offset), "no_topic" (on the rim). None when
    # placed in full.
    approximate: str | None = None


def topic_key(name_or_key: str | None) -> str | None:
    """A topic's key from its key or its display name; None if neither."""

    if not name_or_key:
        return None

    if name_or_key in TOPICS:
        return name_or_key

    return _KEY_OF_NAME.get(name_or_key.casefold())


@lru_cache(maxsize=1)
def _slots() -> tuple[dict[str, float], dict[str, float]]:
    """
    Each topic's slot centre and each group's sector centre, in slots
    from the top, clockwise; the first group centred on the top.
    """

    topic_at: dict[str, float] = {}
    group_at: dict[str, float] = {}
    cursor = 0.0

    for group in GROUP_ORDER:

        start = cursor

        for key in TOPIC_GROUPS[group]:
            topic_at[key] = cursor + 0.5
            cursor += 1.0

        group_at[group] = (start + cursor) / 2
        cursor += GROUP_GAP

    first = group_at[GROUP_ORDER[0]]

    return (
        {key: at - first for key, at in topic_at.items()},
        {group: at - first for group, at in group_at.items()},
    )


def _angle(slot: float) -> float:
    return math.pi / 2 - slot * SLOT


def group_angle(group: str) -> float:
    """The centre of a group's sector, in radians: the first at the top, then clockwise."""

    return _angle(_slots()[1][group])


def group_span(group: str) -> float:
    """How wide a group's sector is, in radians: one slot per topic."""

    return len(TOPIC_GROUPS[group]) * SLOT


@lru_cache(maxsize=1)
def anchors() -> dict[str, Anchor]:
    """Every topic's anchor, by key, in src/config/topics.py's group order."""

    topic_at, _ = _slots()
    placed: dict[str, Anchor] = {}

    for index, key in enumerate(key for group in GROUP_ORDER for key in TOPIC_GROUPS[group]):

        angle = _angle(topic_at[key])
        radius = OUTER_RADIUS if index % 2 == 0 else INNER_RADIUS

        placed[key] = Anchor(
            key=key,
            name=TOPICS[key].name,
            group=GROUP_OF[key],
            x=radius * math.cos(angle),
            y=radius * math.sin(angle),
        )

    return placed


def frame() -> dict:
    """The fixed part of the map: groups and topic anchors, for drawing."""

    return {
        "layout": LAYOUT_VERSION,
        "groups": [
            {
                "key": group,
                "name": TOPIC_GROUP_NAMES.get(group, group),
                "angle": round(group_angle(group), 6),
                "span": round(group_span(group), 6),
            }
            for group in GROUP_ORDER
        ],
        "topics": [
            {"key": a.key, "name": a.name, "group": a.group, "x": round(a.x, 4), "y": round(a.y, 4)}
            for a in anchors().values()
        ],
    }


@lru_cache(maxsize=4)
def _basis(dimension: int) -> np.ndarray:
    """An orthonormal (dimension x 2) basis, the same for every call with this version."""

    rng = np.random.default_rng(BASIS_SEED + dimension)
    q, _ = np.linalg.qr(rng.standard_normal((dimension, 2)))

    return q


def _squash(z: np.ndarray, radius: float) -> tuple[float, float]:
    """A 2D offset of any size into one shorter than `radius`, nearly linear for a typical one."""

    length = float(np.hypot(z[0], z[1]))

    if length == 0.0:
        return 0.0, 0.0

    scale = radius * math.tanh(length / SPREAD) / length

    return float(z[0] * scale), float(z[1] * scale)


def embedding_offset(vector) -> tuple[float, float] | None:
    """
    The article's own place within its cluster: its unit vector projected
    on the fixed basis. A unit vector's projection on a random unit
    direction has a spread of ~1/sqrt(dimension), so it is scaled by
    sqrt(dimension) to ~N(0, 1) (0.78 a side on real claims) and squashed
    into CLUSTER_RADIUS (SPREAD). Two
    similar articles have nearby projections and sit side by side.
    """

    if vector is None:
        return None

    v = np.asarray(vector, dtype=np.float64).ravel()

    norm = float(np.linalg.norm(v))

    if v.size < 2 or norm == 0.0 or not math.isfinite(norm):
        return None

    z = (v / norm) @ _basis(v.size) * math.sqrt(v.size)

    return _squash(z, CLUSTER_RADIUS)


def _hash_offset(seed: str, radius: float) -> tuple[float, float]:
    """A deterministic offset for an article with no vector, so such articles do not stack."""

    digest = hashlib.sha256(f"{LAYOUT_VERSION}:{seed}".encode()).digest()
    angle = int.from_bytes(digest[:4], "big") / 2**32 * 2 * math.pi
    distance = math.sqrt(int.from_bytes(digest[4:8], "big") / 2**32) * radius

    return distance * math.cos(angle), distance * math.sin(angle)


def ranked_topics(topics) -> list[tuple[str, float]]:
    """
    (key, confidence), highest first, for the topics the lake gives as
    [{"topic": name, "confidence": c}, ...]; unknown names and missing
    confidences dropped.
    """

    ranked = []

    for item in topics or []:

        if not isinstance(item, dict):
            continue

        key = topic_key(item.get("topic"))
        confidence = item.get("confidence")

        if key is None or not isinstance(confidence, (int, float)):
            continue

        ranked.append((key, float(confidence)))

    ranked.sort(key=lambda pair: (-pair[1], pair[0]))

    # One entry per topic: the lake can name a topic twice.
    seen: set[str] = set()

    return [pair for pair in ranked if not (pair[0] in seen or seen.add(pair[0]))]


def place(article_id: str, topics, vector=None, primary: str | None = None) -> Placement:
    """
    Where one article goes. `topics` as the lake stores them; `vector`
    its embedding, if any; `primary` the record's primary topic, used
    only when `topics` gives none.
    """

    ranked = ranked_topics(topics)

    if not ranked and topic_key(primary):
        ranked = [(topic_key(primary), 1.0)]

    if not ranked:
        dx, dy = _hash_offset(article_id, 1.0)
        angle = math.atan2(dy, dx)
        return Placement(
            x=RIM_RADIUS * math.cos(angle),
            y=RIM_RADIUS * math.sin(angle),
            group=None,
            topics=(),
            approximate="no_topic",
        )

    table = anchors()
    main_key, main_confidence = ranked[0]
    main = table[main_key]

    pull_x = pull_y = 0.0

    for key, confidence in ranked[1:]:

        tie = 1.0 - (main_confidence - confidence) / TIE_MARGIN
        other = table[key]
        distance = math.hypot(other.x - main.x, other.y - main.y)

        if tie > 0 and distance > 0:
            pull_x += (other.x - main.x) / distance * MAX_PULL * min(tie, 1.0)
            pull_y += (other.y - main.y) / distance * MAX_PULL * min(tie, 1.0)

    pulled = math.hypot(pull_x, pull_y)

    if pulled > MAX_PULL:
        pull_x, pull_y = pull_x / pulled * MAX_PULL, pull_y / pulled * MAX_PULL

    x = main.x + pull_x
    y = main.y + pull_y

    offset = embedding_offset(vector)
    approximate = None

    if offset is None:
        offset = _hash_offset(article_id, CLUSTER_RADIUS)
        approximate = "no_vector"

    return Placement(
        x=x + offset[0],
        y=y + offset[1],
        group=GROUP_OF.get(main_key),
        topics=tuple(key for key, _ in ranked),
        approximate=approximate,
    )
