from datetime import date

import numpy as np
import pytest

from src.config import for_you as config
from src.config.topics import TOPICS
from src.services.news_map.for_you import ReaderProfile, lowered, rank, reader_weights
from src.services.news_map.index import Entity, MapArticle, MapIndex
from src.services.news_map.layout import anchors

TODAY = date(2026, 10, 29)


def story(i, topic, source=None, day="2026-10-29", entities=(), vector=None):
    a = anchors()[topic]
    return MapArticle(
        id=f"{i:016x}", record_id=f"r{i}", title=f"{TOPICS[topic].name} story {i}", language="en", day=day,
        source=source or f"Outlet {i}", verdict="TRUE", group=a.group, topics=((topic, 0.5),),
        entities=tuple(entities), claims={}, evidence=frozenset(), x=a.x, y=a.y, approximate=None,
        sort_at=float(i * 7200), vector=None if vector is None else np.asarray(vector, dtype=np.float32),
    )


def context_of(articles, tmp_path):
    index = MapIndex(None, None, None)
    index.refresh = lambda: None
    index._rebuild(articles)
    return index.search_context()


def ids(result):
    return [item["id"] for item in result["items"]]


def test_the_weights_sum_to_one_and_still_do_after_not_interested():

    assert sum(config.FOR_YOU_WEIGHTS.values()) == pytest.approx(1.0)

    factors = lowered(lowered({}, "topic"), "topic")
    weights = reader_weights(factors)

    assert sum(weights.values()) == pytest.approx(1.0)
    assert weights["topic"] < config.FOR_YOU_WEIGHTS["topic"]
    assert factors["topic"] == pytest.approx(config.NOT_INTERESTED_STEP ** 2)


def test_a_factor_never_drops_below_its_floor():

    factors = {}
    for _ in range(30):
        factors = lowered(factors, "entity")

    assert factors["entity"] == pytest.approx(config.NOT_INTERESTED_FLOOR)


def test_a_climate_followers_first_ten_are_mostly_climate_but_not_only(tmp_path):

    others = [k for k in anchors() if k != "climate"]
    articles = [story(i, "climate") for i in range(30)] + [story(100 + i, others[i % len(others)]) for i in range(30)]

    result = rank(context_of(articles, tmp_path), ReaderProfile.of([{"kind": "topic", "key": "climate"}]), today=TODAY)
    first = [item["title"].startswith(TOPICS["climate"].name) for item in result["items"][:10]]

    assert sum(first) == config.MAX_FROM_A_FOLLOWED_TOPIC
    assert not all(first)


def test_another_topic_takes_at_most_three_of_the_first_ten(tmp_path):

    articles = [story(i, "space") for i in range(20)] + [story(100 + i, "climate", day="2026-10-20") for i in range(20)]

    result = rank(context_of(articles, tmp_path), ReaderProfile.of([{"kind": "topic", "key": "climate"}]), today=TODAY)
    first = [item["title"].split(" story")[0] for item in result["items"][:10]]

    assert first.count(TOPICS["space"].name) <= config.MAX_FROM_ANOTHER_TOPIC


def test_a_followed_name_brings_its_stories(tmp_path):

    ada = Entity(key="person:ada lovelace", name="Ada Lovelace", type="person")
    articles = [story(i, "space") for i in range(10)] + [story(50, "heritage", entities=[ada])]

    result = rank(context_of(articles, tmp_path), ReaderProfile.of([{"kind": "entity", "key": ada.key}]), today=TODAY)

    assert result["items"][0]["id"] == f"{50:016x}"
    assert "you follow Ada Lovelace" in result["items"][0]["reasons"]


def test_two_stories_from_one_outlet_within_an_hour_are_one(tmp_path):

    a = story(1, "climate", source="Same Outlet")
    b = story(2, "climate", source="Same Outlet")
    b = MapArticle(**{**b.__dict__, "sort_at": a.sort_at + 1800})

    result = rank(context_of([a, b, story(3, "climate")], tmp_path), ReaderProfile.of([{"kind": "topic", "key": "climate"}]), today=TODAY)

    assert len([i for i in result["items"] if i["source"] == "Same Outlet"]) == 1


def test_a_hidden_story_never_returns_and_a_saved_one_is_not_offered(tmp_path):

    articles = [story(i, "climate") for i in range(5)]
    hidden, saved = articles[0].id, articles[1].id

    result = rank(context_of(articles, tmp_path), ReaderProfile.of([{"kind": "topic", "key": "climate"}], saved=[saved], hidden=[hidden]), today=TODAY)

    assert hidden not in ids(result) and saved not in ids(result)


def test_the_parts_shown_add_up_to_the_score(tmp_path):

    ada = Entity(key="person:ada lovelace", name="Ada Lovelace", type="person")
    articles = [story(i, "climate", entities=[ada] if i % 2 else (), day=f"2026-10-{20 + i}") for i in range(8)]

    result = rank(context_of(articles, tmp_path), ReaderProfile.of([{"kind": "topic", "key": "climate"}, {"kind": "entity", "key": ada.key}]), today=TODAY)

    for item in result["items"]:
        assert sum(item["parts"].values()) == pytest.approx(item["score"], abs=1e-3)


def test_saved_stories_bring_the_ones_near_them(tmp_path):

    rng = np.random.default_rng(0)
    base = rng.standard_normal(1024)
    near = [base + 0.3 * rng.standard_normal(1024) for _ in range(3)]
    far = [rng.standard_normal(1024) for _ in range(3)]
    articles = [story(i, "space", vector=v) for i, v in enumerate(near + far)]

    result = rank(context_of(articles, tmp_path), ReaderProfile.of([], saved=[articles[0].id]), today=TODAY)
    top = result["items"][0]

    assert top["id"] in {articles[1].id, articles[2].id}
    assert top["parts"]["nearness"] > 0 and "close to stories you saved" in top["reasons"]


def test_with_nothing_followed_it_is_the_newest_stories_and_says_so(tmp_path):

    articles = [story(i, "space", day=f"2026-10-{10 + i}") for i in range(5)]

    result = rank(context_of(articles, tmp_path), ReaderProfile.of([]), today=TODAY)

    assert result["coldStart"] is True
    assert [item["day"] for item in result["items"]] == sorted((a.day for a in articles), reverse=True)
