import sqlite3

import numpy as np
import pytest

from src.config.topics import TOPICS
from src.services.accounts import reader_data
from src.services.accounts.reader_data import ReaderData
from src.services.accounts.service import AccountError
from src.services.news_map.index import MapIndex
from src.services.reader.index import ReaderIndex
from src.services.reader.views import SourceNames

from tests.services.accounts.accounts_fixtures import make_service
from tests.services.reader.reader_lake import make_lake, publish

PASSWORD = "correct horse battery"


def unit(seed):
    v = np.random.default_rng(seed).standard_normal(1024)
    return list(v / np.linalg.norm(v))


@pytest.fixture
def world(tmp_path):
    lake = make_lake(tmp_path / "lake")
    index = MapIndex(lake, ReaderIndex(lake), SourceNames())
    service = make_service(tmp_path)
    data = ReaderData(service.store, index)
    return lake, index, service, data


def put(lake, slug, title, topic="climate", seed=0, **kwargs):
    publish(lake, f"https://www.bbc.com/news/{slug}-a-long-enough-slug", title=title,
            topics=[(TOPICS[topic].name, 0.6)], embedding=unit(seed), checks=[], **kwargs)


def ids_by_title(index):
    return {a.title: a.id for a in index.articles()}


def test_a_reader_follows_groups_topics_and_names_that_exist(world):

    lake, index, service, data = world
    put(lake, "one", "One", entities={"person": ["Ada Lovelace"]})
    _, session = service.register("ada", PASSWORD, None, "c")

    data.follow(session, "group", "environment")
    data.follow(session, "topic", "space")
    items = data.follow(session, "entity", "person:ada lovelace")

    assert [(i["kind"], i["label"]) for i in items] == [
        ("group", "Environment"), ("topic", TOPICS["space"].name), ("entity", "Ada Lovelace"),
    ]

    for kind, key in (("group", "sport"), ("topic", "astrology"), ("entity", "person:nobody"), ("planet", "mars")):
        with pytest.raises(AccountError):
            data.follow(session, kind, key)


def test_choices_made_signed_out_import_and_what_no_longer_exists_is_skipped(world):

    lake, index, service, data = world
    _, session = service.register("ada", PASSWORD, None, "c")

    items = data.replace_interests(session, [
        {"kind": "topic", "key": "space"}, {"kind": "topic", "key": "gone"}, {"kind": "group", "key": "health"},
    ])

    assert [i["key"] for i in items] == ["space", "health"]


def test_only_a_published_story_can_be_saved(world):

    lake, index, service, data = world
    put(lake, "pub", "Published")
    put(lake, "rej", "Rejected", seed=1, validation_passed=False)
    _, session = service.register("ada", PASSWORD, None, "c")

    saved = data.save(session, ids_by_title(index)["Published"])
    assert [s["title"] for s in saved] == ["Published"]

    for article_id in ("0" * 16, "not-an-id", "../../etc"):
        with pytest.raises(AccountError):
            data.save(session, article_id)


def test_a_connection_joins_two_stories_or_a_story_and_a_name_with_a_note(world):

    lake, index, service, data = world
    put(lake, "a", "A", entities={"person": ["Ada Lovelace"]})
    put(lake, "b", "B", topic="space", seed=1)
    _, session = service.register("ada", PASSWORD, None, "c")
    ids = ids_by_title(index)

    data.connect(session, ids["A"], "article", ids["B"], "Same valley, years apart")
    items = data.connect(session, ids["B"], "entity", "person:ada lovelace", "")

    assert [(c["from"], c["toKind"], c["to"], c["note"]) for c in items] == [
        (ids["A"], "article", ids["B"], "Same valley, years apart"),
        (ids["B"], "entity", "person:ada lovelace", ""),
    ]

    with pytest.raises(AccountError):
        data.connect(session, ids["A"], "article", ids["A"], "")
    with pytest.raises(AccountError):
        data.connect(session, ids["A"], "article", ids["B"], "x" * 281)
    with pytest.raises(AccountError):
        data.connect(session, ids["A"], "planet", "mars", "")


def test_connections_are_capped(world, monkeypatch):

    lake, index, service, data = world
    put(lake, "a", "A")
    put(lake, "b", "B", topic="space", seed=1)
    _, session = service.register("ada", PASSWORD, None, "c")
    ids = ids_by_title(index)
    monkeypatch.setattr(reader_data, "MAX_CONNECTIONS", 2)

    data.connect(session, ids["A"], "article", ids["B"], "")
    data.connect(session, ids["B"], "article", ids["A"], "")

    with pytest.raises(AccountError, match="At most 2"):
        data.connect(session, ids["A"], "article", ids["B"], "again")


def test_a_personal_connection_never_reaches_the_shared_links_or_another_reader(world):

    lake, index, service, data = world
    put(lake, "a", "A")
    put(lake, "b", "B", topic="space", seed=1)
    _, ada = service.register("ada", PASSWORD, None, "c")
    _, grace = service.register("grace", PASSWORD, None, "c2")
    ids = ids_by_title(index)

    data.connect(ada, ids["A"], "article", ids["B"], "mine")

    assert ids["B"] not in [row["id"] for row in index.links(ids["A"])["related"]]
    assert data.connections(grace) == []


def test_export_and_delete_cover_what_a_reader_keeps(world):

    lake, index, service, data = world
    put(lake, "a", "A")
    put(lake, "b", "B", topic="space", seed=1)
    _, session = service.register("ada", PASSWORD, None, "c")
    ids = ids_by_title(index)

    data.follow(session, "topic", "space")
    data.save(session, ids["A"])
    data.connect(session, ids["A"], "article", ids["B"], "note")

    exported = service.export(session)
    assert len(exported["interests"]) == len(exported["saved"]) == len(exported["connections"]) == 1

    service.delete(session, PASSWORD)

    with sqlite3.connect(service.store.path) as db:
        for table in ("interests", "saved", "connections"):
            assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_not_interested_hides_the_story_and_lowers_that_part_for_this_reader_alone(world):

    lake, index, service, data = world
    put(lake, "a", "A")
    _, ada = service.register("ada", PASSWORD, None, "c")
    _, grace = service.register("grace", PASSWORD, None, "c2")
    story = ids_by_title(index)["A"]

    feed = data.not_interested(ada, story, "topic")
    feed = data.not_interested(ada, story, "topic")

    assert feed["hidden"] == [story]
    assert feed["factors"]["topic"] == pytest.approx(0.64)
    assert data.feed(grace) == {"hidden": [], "factors": {}}

    with pytest.raises(AccountError):
        data.not_interested(ada, story, "astrology")

    exported = service.export(ada)
    assert len(exported["hidden"]) == 1 and len(exported["feed_factors"]) == 1
