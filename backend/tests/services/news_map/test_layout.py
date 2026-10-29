import math

import numpy as np
import pytest

from src.config.topics import GROUP_OF, TOPIC_GROUPS, TOPICS
from src.services.news_map import layout
from src.services.news_map.layout import (
    CLUSTER_RADIUS,
    GROUP_ORDER,
    MAX_PULL,
    anchors,
    group_angle,
    group_span,
    place,
    topic_key,
)


def angle_gap(a: float, b: float) -> float:
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi)


def nearest_anchor(x: float, y: float) -> str:
    return min(anchors().values(), key=lambda a: math.hypot(a.x - x, a.y - y)).key


def unit(seed: int, dimension: int = 1024) -> list[float]:
    vector = np.random.default_rng(seed).standard_normal(dimension)
    return list(vector / np.linalg.norm(vector))


def test_every_topic_has_an_anchor_inside_its_groups_sector():

    table = anchors()

    assert set(table) == set(TOPICS)

    for key, anchor in table.items():
        assert anchor.group == GROUP_OF[key]
        assert angle_gap(math.atan2(anchor.y, anchor.x), group_angle(anchor.group)) < group_span(anchor.group) / 2


def test_anchors_are_far_enough_apart_for_their_clusters_not_to_meet():
    """Even an article pulled as far as a tie pulls it stays nearer its own anchor."""

    points = list(anchors().values())

    closest = min(
        math.hypot(a.x - b.x, a.y - b.y) for i, a in enumerate(points) for b in points[i + 1:]
    )

    assert closest > 2 * (CLUSTER_RADIUS + MAX_PULL)


def test_a_topic_is_known_by_its_key_or_its_display_name():

    assert topic_key("cities") == "cities"
    assert topic_key("Cities & Society") == "cities"
    assert topic_key("cities & society") == "cities"
    assert topic_key("Environment") is None  # a group, not a topic
    assert topic_key(None) is None


def test_the_same_article_is_always_in_the_same_place():

    topics = [{"topic": "Climate Action", "confidence": 0.5}]
    vector = unit(1)

    first = place("a1", topics, vector)
    again = place("a1", topics, vector)

    assert (first.x, first.y) == (again.x, again.y)


def test_compressed_confidences_still_put_an_article_in_its_main_topics_section():
    """
    The first article read on 29 Oct: three topics in three groups,
    0.373, 0.360 and 0.350. A mean of their anchors would put it near the
    centre; the main topic must stay the nearest anchor.
    """

    topics = [
        {"topic": "Entertainment", "confidence": 0.3734},
        {"topic": "Sustainability", "confidence": 0.3598},
        {"topic": "Cities & Society", "confidence": 0.3502},
    ]

    placed = place("first", topics, unit(2))

    assert placed.group == "culture"
    assert placed.topics == ("entertainment", "sustainability", "cities")
    assert nearest_anchor(placed.x, placed.y) == "entertainment"
    assert math.hypot(placed.x, placed.y) > 0.3


def test_an_article_of_two_groups_tied_lies_between_their_anchors():

    a, b = anchors()["climate"], anchors()["medicine"]

    placed = place("tie", [
        {"topic": a.name, "confidence": 0.5},
        {"topic": b.name, "confidence": 0.5},
    ])

    between = math.hypot(a.x - b.x, a.y - b.y)

    assert math.hypot(placed.x - a.x, placed.y - a.y) < between
    assert math.hypot(placed.x - b.x, placed.y - b.y) < between
    # Pulled towards the second, but nearer the first.
    assert math.hypot(placed.x - a.x, placed.y - a.y) < math.hypot(placed.x - b.x, placed.y - b.y)


def test_a_second_topic_well_below_the_first_does_not_move_it():

    alone = place("x", [{"topic": "Space", "confidence": 0.6}], unit(3))
    with_far_second = place("x", [
        {"topic": "Space", "confidence": 0.6},
        {"topic": "Nutrition", "confidence": 0.6 - layout.TIE_MARGIN - 0.01},
    ], unit(3))

    assert (alone.x, alone.y) == (with_far_second.x, with_far_second.y)


def test_similar_articles_sit_closer_than_unrelated_ones():

    base = np.asarray(unit(4))
    near = base + 0.05 * np.asarray(unit(5))
    far = np.asarray(unit(6))

    topics = [{"topic": "Space", "confidence": 0.6}]

    p_base = place("b", topics, list(base))
    p_near = place("n", topics, list(near))
    p_far = place("f", topics, list(far))

    assert math.hypot(p_base.x - p_near.x, p_base.y - p_near.y) < math.hypot(p_base.x - p_far.x, p_base.y - p_far.y)


def test_the_embedding_moves_an_article_less_than_a_clusters_radius():

    anchor = anchors()["space"]

    for seed in range(50):
        placed = place(str(seed), [{"topic": "Space", "confidence": 0.6}], unit(seed))
        assert math.hypot(placed.x - anchor.x, placed.y - anchor.y) < CLUSTER_RADIUS


def test_without_a_vector_it_is_placed_by_its_topics_and_says_so():

    placed = place("nv", [{"topic": "Space", "confidence": 0.6}], None)

    assert placed.approximate == "no_vector"
    assert nearest_anchor(placed.x, placed.y) == "space"
    assert place("nv", [{"topic": "Space", "confidence": 0.6}], None) == placed


def test_without_a_topic_it_goes_on_the_rim_and_says_so():

    placed = place("nt", [{"topic": "Not a topic", "confidence": 0.9}], unit(7))

    assert placed.approximate == "no_topic"
    assert placed.group is None
    assert math.hypot(placed.x, placed.y) == pytest.approx(layout.RIM_RADIUS)


def test_the_primary_topic_places_it_when_the_list_is_empty():

    placed = place("p", [], unit(8), primary=TOPICS["medicine"].name)

    assert placed.group == "health"


def test_the_groups_go_clockwise_from_the_top_in_their_declared_order():

    assert GROUP_ORDER == tuple(TOPIC_GROUPS)
    assert group_angle(GROUP_ORDER[0]) == pytest.approx(math.pi / 2)
    assert group_angle(GROUP_ORDER[1]) < group_angle(GROUP_ORDER[0])
