import numpy as np
import pytest

from src.services.selection.mission_screen import Reading
from src.services.selection.ranking import (
    NEWS_RANGE,
    RECORD_PRIOR,
    SAME_STORY,
    WEIGHTS,
    Standing,
    best_first,
    news_part,
    one_per_story,
    rank,
    record_part,
)


def reading(impact: float, off: float = 0.45) -> Reading:

    return Reading(nearest_topic="arts", topic=0.5, nearest_off="politics", off=off, impact=impact)


MIDDLE = 0.45 + sum(NEWS_RANGE) / 2


def test_the_weights_sum_to_one_so_a_score_is_between_zero_and_one():

    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_news_is_how_much_nearer_positive_impact_than_anything_off_mission():

    low, high = NEWS_RANGE

    assert news_part(reading(0.45 + low)) == pytest.approx(0.0)
    assert news_part(reading(0.45 + high)) == pytest.approx(1.0)
    assert news_part(reading(MIDDLE)) == pytest.approx(0.5)


def test_news_beyond_the_measured_range_is_held_at_its_ends():

    assert news_part(reading(0.95)) == 1.0
    assert news_part(reading(0.05)) == 0.0
    assert news_part(None) is None


def test_a_source_record_is_the_share_kept_smoothed_towards_the_prior():

    assert record_part(Standing(reliability=0.9)) == pytest.approx(RECORD_PRIOR)
    assert record_part(Standing(reliability=0.9, judged=15, kept=15)) == pytest.approx(0.95)
    assert record_part(Standing(reliability=0.9, judged=15, kept=8)) == pytest.approx(0.6)


def test_a_positive_outlet_has_a_full_record_without_being_judged():

    assert record_part(Standing(reliability=0.65, positive_editorial=True)) == 1.0


def test_a_candidate_with_nothing_read_counts_as_middling():

    standing = Standing(reliability=0.9, judged=10, kept=8)
    unread = rank(None, standing)

    assert unread["news"] is None
    # Both rounded to three places from about 0.6125.
    assert unread["score"] == pytest.approx(rank(reading(MIDDLE), standing)["score"], abs=2e-3)


def test_the_round_records_the_rating_itself_and_the_other_parts_scaled():

    parts = rank(reading(MIDDLE), Standing(reliability=0.94, judged=5, kept=5))

    assert parts == {"score": pytest.approx(0.6 * 0.5 + 0.25 * 0.9 + 0.15 * 0.85, abs=1e-3), "news": 0.5, "record": 0.9, "reliability": 0.94}


def test_reliability_has_the_smallest_say():
    """The rating does not tell a positive story from another (AUC 0.49): it settles near-ties only."""

    good_story_low_rating = rank(reading(0.52), Standing(reliability=0.65, judged=10, kept=10))
    weak_story_high_rating = rank(reading(0.44), Standing(reliability=1.0, judged=10, kept=10))

    assert good_story_low_rating["score"] > weak_story_high_rating["score"]


def test_best_first_keeps_ties_in_their_order():

    a, b, c = ({"url": url, "rank": {"score": score}} for url, score in (("a", 0.5), ("b", 0.7), ("c", 0.5)))

    assert [candidate["url"] for candidate in best_first([a, b, c])] == ["b", "a", "c"]


# ----------------------------------------------------------------------
# One story, once
# ----------------------------------------------------------------------


def unit(*values: float) -> np.ndarray:

    vector = np.asarray(values, dtype=float)

    return vector / np.linalg.norm(vector)


def angled(cosine: float) -> np.ndarray:
    """A unit vector at `cosine` to (1, 0, 0)."""

    return np.asarray([cosine, (1 - cosine ** 2) ** 0.5, 0.0])


def listed(*urls: str) -> list[dict]:

    return [{"url": url} for url in urls]


def test_the_same_story_again_goes_after_every_distinct_one():
    """2026-10-06: the physics Nobel took 8 of a round's first twenty places."""

    nobel = unit(1, 0, 0)
    vectors = {
        "guardian-nobel": nobel,
        "bbc-nobel": angled(SAME_STORY + 0.05),
        "mit-telescope": unit(0, 1, 0),
        "sinc-planet": unit(0, 0, 1),
    }

    ranked = one_per_story(listed("guardian-nobel", "bbc-nobel", "mit-telescope", "sinc-planet"), vectors)

    assert [c["url"] for c in ranked] == ["guardian-nobel", "mit-telescope", "sinc-planet", "bbc-nobel"]
    assert ranked[-1]["sameStoryAs"] == "guardian-nobel"
    assert "sameStoryAs" not in ranked[0]


def test_a_version_near_any_of_a_storys_versions_joins_it():
    """SINC's Spanish Nobel was 0.73 from the Guardian's, 0.79 from La Vanguardia's."""

    vectors = {
        "guardian": unit(1, 0, 0),
        "vanguardia": angled(0.8),
        # 0.6 from the guardian, about 0.96 from vanguardia.
        "sinc": angled(0.6),
    }

    ranked = one_per_story(listed("guardian", "vanguardia", "sinc"), vectors)

    assert [c.get("sameStoryAs") for c in ranked] == [None, "guardian", "guardian"]


def test_stories_below_the_threshold_and_unread_candidates_stay_apart():

    vectors = {"nature-ai": unit(1, 0, 0), "nature-preprints": angled(SAME_STORY - 0.06)}

    ranked = one_per_story(listed("nature-ai", "unread", "nature-preprints"), vectors)

    assert [c["url"] for c in ranked] == ["nature-ai", "unread", "nature-preprints"]
    assert not any("sameStoryAs" in c for c in ranked)
