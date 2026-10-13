import numpy as np
import pytest

from src.services.selection.mission_screen import Reading
from src.services.selection.ranking import (
    DEFAULT_TOPIC_EMPHASIS,
    GROUP_FIT,
    NEWS_RANGE,
    TOPIC_RANGE,
    RECORD_PRIOR,
    SAME_STORY,
    WITHOUT_TOPIC,
    Standing,
    applied_emphasis,
    best_first,
    described,
    fitting_first,
    group_fit,
    news_part,
    one_per_story,
    ordered,
    rank,
    record_part,
    topic_part,
    weights,
)


def reading(impact: float, off: float = 0.45) -> Reading:

    return Reading(nearest_topic="arts", topic=0.5, nearest_off="politics", off=off, impact=impact)


MIDDLE = 0.45 + sum(NEWS_RANGE) / 2


@pytest.mark.parametrize("emphasis", [None, 0.0, 0.1, 0.25, 0.5, 0.6, 0.75, 0.9, 1.0])
def test_the_weights_sum_to_one_at_every_emphasis_so_a_score_is_between_zero_and_one(emphasis):
    """The emphasis moves weight between two parts; it never sets one alone and de-normalises the score."""

    assert sum(weights(emphasis).values()) == pytest.approx(1.0)


def test_the_emphasis_splits_the_storys_share_and_leaves_the_sources_alone():

    for emphasis in (0.0, 0.3, 1.0):
        weighted = weights(emphasis)
        assert weighted["news"] + weighted["topic"] == pytest.approx(0.6)
        assert (weighted["record"], weighted["reliability"]) == (0.25, 0.15)


def test_no_emphasis_on_the_topic_is_the_2026_10_06_score():

    assert weights(0.0) == pytest.approx({"news": 0.6, "topic": 0.0, "record": 0.25, "reliability": 0.15})


def test_by_default_the_topic_weighs_more_than_positive_impact():
    """A round about science should list science stories first, positive ones among them."""

    assert DEFAULT_TOPIC_EMPHASIS > 0.5
    assert weights(None) == weights(DEFAULT_TOPIC_EMPHASIS)
    assert weights(None)["topic"] > weights(None)["news"]


@pytest.mark.parametrize("emphasis", [-0.01, 1.01, 2.0])
def test_an_emphasis_outside_zero_to_one_is_refused(emphasis):

    with pytest.raises(ValueError, match="between 0 and 1"):
        weights(emphasis)

    with pytest.raises(ValueError):
        rank(reading(MIDDLE), Standing(reliability=0.9), fit=0.0, emphasis=emphasis)


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

    # The default emphasis: news 0.24, topic 0.36 (unread: 0.5), record 0.25, reliability 0.15.
    assert parts == {
        "score": pytest.approx(0.24 * 0.5 + 0.36 * 0.5 + 0.25 * 0.9 + 0.15 * 0.85, abs=1e-3),
        "news": 0.5,
        "topic": None,
        "record": 0.9,
        "reliability": 0.94,
    }


def test_reliability_has_the_smallest_say_where_there_is_no_topic_to_weigh():
    """
    The rating does not tell a positive story from another (AUC 0.49): it
    settles near-ties only. At emphasis 0 - a round with no topic signal -
    the story has all of its 0.6.
    """

    good_story_low_rating = rank(reading(0.52), Standing(reliability=0.65, judged=10, kept=10), emphasis=WITHOUT_TOPIC)
    weak_story_high_rating = rank(reading(0.44), Standing(reliability=1.0, judged=10, kept=10), emphasis=WITHOUT_TOPIC)

    assert good_story_low_rating["score"] > weak_story_high_rating["score"]


def test_reliability_is_still_the_smallest_weight_by_default():

    weighted = weights(None)

    assert weighted["reliability"] == min(weighted.values())


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


# ----------------------------------------------------------------------
# The groups asked for, first
# ----------------------------------------------------------------------

HEALTH = ["medicine", "mental_health", "nutrition", "fitness", "public_health"]


def near(**topics: float) -> Reading:
    """A reading whose nearness to each topic is given; every other topic at 0.2."""

    from src.config.topics import TOPICS

    similarities = {topic: 0.2 for topic in TOPICS}
    similarities.update(topics)

    return Reading(
        nearest_topic=max(similarities, key=similarities.get), topic=max(similarities.values()),
        nearest_off="politics", off=0.3, impact=0.4, topics=similarities,
    )


def test_a_story_of_the_groups_asked_for_fits_and_one_of_another_does_not():
    """2026-10-09, a Health round: the chemistry Nobel came nearest "research"."""

    assert group_fit(near(public_health=0.6, research=0.5), HEALTH) == pytest.approx(0.1)
    assert group_fit(near(research=0.6, medicine=0.45), HEALTH) == pytest.approx(-0.15)


def test_there_is_no_fit_without_a_reading_or_when_every_topic_was_asked_for():

    from src.config.topics import TOPICS

    assert group_fit(None, HEALTH) is None
    assert group_fit(reading(0.5), HEALTH) is None
    assert group_fit(near(medicine=0.6), list(TOPICS)) is None


def test_a_candidate_that_fits_another_group_goes_after_those_that_fit():

    ranked = fitting_first(
        listed("nobel-chemistry", "aids-prevention", "hachimaki", "menopause"),
        fits={"nobel-chemistry": -0.15, "aids-prevention": 0.08, "hachimaki": GROUP_FIT, "menopause": 0.02},
        nearest={"nobel-chemistry": "research", "aids-prevention": "public_health", "hachimaki": "fitness", "menopause": "medicine"},
    )

    # Exactly at the line still fits; the rest keep their order.
    assert [c["url"] for c in ranked] == ["aids-prevention", "hachimaki", "menopause", "nobel-chemistry"]
    assert ranked[-1]["otherGroup"] == "science"
    assert not any("otherGroup" in c for c in ranked[:-1])


def test_a_candidate_without_a_fit_stays_where_it_is():

    ranked = fitting_first(listed("unread", "breakfast"), fits={"breakfast": -0.12}, nearest={"breakfast": "nutrition"})

    assert [c["url"] for c in ranked] == ["unread", "breakfast"]
    assert ranked[1]["otherGroup"] == "health"



def test_the_topic_part_is_the_fit_scaled_and_absent_without_groups():

    low, high = TOPIC_RANGE

    assert topic_part(low) == 0.0 and topic_part(high) == 1.0
    assert topic_part(GROUP_FIT) == 0.0
    assert topic_part((low + high) / 2) == pytest.approx(0.5)
    assert topic_part(None) is None


def test_of_two_stories_alike_the_one_on_the_rounds_topics_ranks_first():
    """2026-10-09: an Environment round's T. rex discoveries (fit -0.03) above a rhino translocation (0.04)."""

    standing = Standing(reliability=0.9, judged=10, kept=9)

    for emphasis in (None, 0.1, 0.9):
        t_rex = rank(reading(0.5), standing, fit=-0.03, emphasis=emphasis)
        rhinos = rank(reading(0.5), standing, fit=0.04, emphasis=emphasis)
        assert rhinos["score"] > t_rex["score"]

    assert rhinos["topic"] == pytest.approx(0.6)


def test_with_positive_impact_first_the_better_story_outranks_the_more_squarely_fitting():
    """Until 2026-10-13 the default: the story counted most."""

    standing = Standing(reliability=0.9, judged=10, kept=9)

    better, squarer = rank(reading(0.52), standing, fit=0.0, emphasis=0.2), rank(reading(0.44), standing, fit=0.10, emphasis=0.2)

    assert better["score"] > squarer["score"]


def test_by_default_the_story_squarely_on_the_topic_outranks_a_more_positive_one_loosely_on_it():
    """2026-10-13: asked for a topic, a person wants stories about it first."""

    standing = Standing(reliability=0.9, judged=10, kept=9)

    loose, square = rank(reading(0.52), standing, fit=0.0), rank(reading(0.44), standing, fit=0.10)

    assert square["score"] > loose["score"]


# A Science round of six, from the 2026-10-09 recheck: three science
# stories of middling positive impact, fully on topic (a fit at or above
# TOPIC_RANGE's 0.10), and three very positive stories of other groups
# whose fit still keeps them among those that fit (above GROUP_FIT).
# (impact, fit, belongs to the round's group)
SCIENCE_ROUND = {
    "spherex-brown-dwarfs": (0.47, 0.12, True),
    "embryo-development": (0.48, 0.10, True),
    "mars-odd-cloud": (0.46, 0.11, True),
    "strangers-put-up-a-tarp": (0.55, -0.04, False),
    "owl-rescued-from-barbed-wire": (0.54, -0.02, False),
    "hospital-dog": (0.53, -0.03, False),
}


def first(emphasis: float, n: int = 3) -> list[str]:
    """The first `n` of SCIENCE_ROUND, ranked and ordered as a round is."""

    standing = Standing(reliability=0.9, judged=10, kept=9)

    candidates = [
        {"url": url, "rank": rank(reading(impact), standing, fit=fit, emphasis=emphasis)}
        for url, (impact, fit, _) in SCIENCE_ROUND.items()
    ]
    fits = {url: fit for url, (_, fit, _) in SCIENCE_ROUND.items()}

    return [c["url"] for c in ordered(candidates, fits, {}, {})][:n]


def test_the_topic_heavy_order_lists_the_groups_stories_first_and_the_positive_heavy_does_not():

    def of_group(urls: list[str]) -> int:
        return sum(1 for url in urls if SCIENCE_ROUND[url][2])

    assert of_group(first(0.9)) == 3
    assert of_group(first(None)) == 3
    assert of_group(first(0.1)) == 0
    # Among the group's own stories the more positive still comes first.
    assert first(0.9)[0] == "embryo-development"


def test_the_emphasis_applies_only_where_there_is_a_topic_to_weigh():

    assert applied_emphasis(None, signal=True) == DEFAULT_TOPIC_EMPHASIS
    assert applied_emphasis(0.2, signal=True) == 0.2
    assert applied_emphasis(0.0, signal=True) == 0.0
    # Every topic asked for, or nothing read: whatever was asked, nothing applies.
    assert applied_emphasis(0.9, signal=False) is None
    assert applied_emphasis(None, signal=False) is None


def test_a_round_records_how_it_was_ranked():

    asked = described(0.3, 0.3)

    assert asked["weights"] == {"news": 0.42, "topic": 0.18, "record": 0.25, "reliability": 0.15}
    assert asked["topicEmphasis"] == {"asked": 0.3, "applied": 0.3, "default": DEFAULT_TOPIC_EMPHASIS}
    assert (asked["sameStory"], asked["groupFit"]) == (SAME_STORY, GROUP_FIT)

    # No topic signal: ranked at WITHOUT_TOPIC, and the round says nothing was applied.
    unweighed = described(0.9, None)

    assert unweighed["weights"]["topic"] == 0.0
    assert unweighed["topicEmphasis"]["applied"] is None and unweighed["topicEmphasis"]["asked"] == 0.9
