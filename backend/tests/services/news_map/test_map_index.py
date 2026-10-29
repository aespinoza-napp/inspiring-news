import gzip
import json
import re
import time
from datetime import datetime

import numpy as np
import pytest

from src.config.topics import TOPICS
from src.models.fact_checker.fact_check import Verdict
from src.services.graph.graph_reader import RELATED_ARTICLES
from src.services.news_map import index as map_index
from src.services.news_map.index import (
    CLAIM_WEIGHT,
    ENTITY_WEIGHT,
    EVIDENCE_WEIGHT,
    TOPIC_WEIGHT,
    Entity,
    MapArticle,
    MapIndex,
    ranked_entities,
)
from src.services.news_map.layout import GROUP_ORDER, anchors
from src.services.reader.index import ReaderIndex
from src.services.reader.views import SourceNames

from tests.services.reader.reader_lake import BODY, SCRAPED_BODY, checked, make_lake, publish


def unit(seed: int) -> list[float]:
    vector = np.random.default_rng(seed).standard_normal(1024)
    return list(vector / np.linalg.norm(vector))


@pytest.fixture
def lake(tmp_path):
    return make_lake(tmp_path)


def make_index(lake) -> MapIndex:
    return MapIndex(lake, ReaderIndex(lake), SourceNames(), {"bbc": "UK"})


def put(lake, slug: str, topic: str = "climate", seed: int = 0, **kwargs):
    return publish(
        lake,
        f"https://www.bbc.com/news/{slug}-story-about-something-good",
        topics=kwargs.pop("topics", [(TOPICS[topic].name, 0.6)]),
        embedding=kwargs.pop("embedding", unit(seed)),
        **kwargs,
    )


def test_every_published_article_is_on_the_map_and_no_other(lake):

    put(lake, "one")
    put(lake, "two", topic="space", seed=1)
    put(lake, "rejected", seed=2, validation_passed=False)

    articles = make_index(lake).articles()

    assert len(articles) == 2
    assert {a.group for a in articles} == {"environment", "science"}


def test_a_new_article_moves_no_other(lake):

    put(lake, "one", seed=1)
    put(lake, "two", topic="space", seed=2)

    index = make_index(lake)
    before = {a.id: (a.x, a.y) for a in index.articles()}

    put(lake, "three", topic="climate", seed=3)

    after = {a.id: (a.x, a.y) for a in index.articles()}

    assert len(after) == 3
    assert {key: after[key] for key in before} == before


def test_the_same_lake_gives_the_same_map(lake):

    put(lake, "one", seed=1)
    put(lake, "two", topic="space", seed=2)

    first = make_index(lake).articles_document()
    second = make_index(lake).articles_document()

    assert first == second


def test_the_document_carries_nothing_the_reader_does_not_show(lake):

    put(lake, "one", seed=1, entities={"person": ["Ada Lovelace"]})

    index = make_index(lake)
    article_id = index.articles()[0].id

    for document in (index.articles_document(), index.entities_document(), index.links(article_id)):

        text = json.dumps(document)

        assert SCRAPED_BODY not in text
        assert BODY[:60] not in text
        assert "lineage" not in text
        assert "embedding" not in text
        assert "record_id" not in text


def test_the_columns_line_up_and_index_into_the_frame(lake):

    put(lake, "one", seed=1, entities={"person": ["Ada Lovelace"], "organization": ["Royal Society"]})
    put(lake, "two", topic="medicine", seed=2)

    document = make_index(lake).articles_document()
    columns = document["articles"]

    assert document["count"] == 2
    assert {len(values) for values in columns.values()} == {2}
    assert len(document["topics"]) == len(TOPICS)
    assert [g["key"] for g in document["groups"]] == list(GROUP_ORDER)

    for groups, topic_refs, entity_refs in zip(columns["g"], columns["t"], columns["e"]):
        assert 0 <= groups < len(GROUP_ORDER)
        assert all(0 <= ref < len(document["topics"]) for ref in topic_refs)
        assert all(0 <= ref < len(document["entities"]) for ref in entity_refs)


def test_one_day_is_its_madrid_day(lake):

    # 22:30 UTC on 28 Oct is 23:30 in Madrid (winter time): the 28th.
    put(lake, "late", seed=1, published_at=datetime.fromisoformat("2026-10-28T22:30:00+00:00"))
    put(lake, "next", seed=2, published_at=datetime.fromisoformat("2026-10-29T09:00:00+00:00"))

    index = make_index(lake)

    assert [a.day for a in index.articles("2026-10-28")] == ["2026-10-28"]
    assert index.articles_document("2026-10-29")["count"] == 1


def test_entities_are_ranked_by_mention_and_glimer_noise_is_dropped():

    ranked = ranked_entities(
        {
            "person": ["D", "J", "Ada Lovelace", "Charles Babbage"],
            "company": ["universidad", "Analytical Engines Ltd"],
        },
        title="Ada Lovelace's notes",
        body="Charles Babbage built it. Charles Babbage again. Analytical Engines Ltd once.",
    )

    assert [e.name for e in ranked] == ["Ada Lovelace", "Charles Babbage", "Analytical Engines Ltd"]


def test_an_entity_is_on_the_map_once_two_articles_name_it(lake):

    put(lake, "one", seed=1, entities={"person": ["Ada Lovelace"], "city": ["Paris"]})
    put(lake, "two", topic="space", seed=2, entities={"person": ["Ada  lovelace"]})

    document = make_index(lake).entities_document()

    assert [row["n"] for row in document["entities"]] == ["Ada Lovelace"]
    assert document["entities"][0]["c"] == 2


def test_two_articles_with_the_same_claim_are_related_most(lake):

    claim = "The valley planted forty thousand trees."

    put(lake, "one", seed=1, title="One", checks=[checked(claim)], entities={"person": ["Ada Lovelace"]})
    put(lake, "two", seed=2, title="Two", checks=[checked(claim)])
    put(lake, "three", topic="space", seed=3, title="Three", entities={"person": ["Ada Lovelace"]}, checks=[])

    index = make_index(lake)
    by_title = {a.title: a for a in index.articles()}

    related = {row["title"]: row for row in index.links(by_title["One"].id)["related"]}

    assert list(related) == ["Two", "Three"]
    assert {via["kind"] for via in related["Two"]["via"]} >= {"claim"}
    assert related["Two"]["score"] >= CLAIM_WEIGHT
    assert [via["kind"] for via in related["Three"]["via"]] == ["entity"]
    assert related["Three"]["score"] == pytest.approx(ENTITY_WEIGHT / 2, abs=1e-4)


def test_a_shared_entity_counts_two_over_the_articles_naming_it(lake):

    for n, seed in enumerate(range(3)):
        put(lake, f"e{n}", topic=["climate", "space", "medicine"][n], seed=seed, checks=[],
            entities={"person": ["Ada Lovelace"]})

    index = make_index(lake)
    article = index.articles()[0]

    weights = [via["weight"] for row in index.links(article.id)["related"] for via in row["via"] if via["kind"] == "entity"]

    assert weights == [pytest.approx(ENTITY_WEIGHT / 3, abs=1e-4)] * 2


def test_the_weights_are_the_graphs_own():
    """The map's related articles must agree with /graph/related's."""

    literals = {
        kind: float(weight)
        for kind, weight in re.findall(r"'(\w+)' AS kind, .*? AS via, ([\d.]+)", RELATED_ARTICLES)
    }

    assert literals == {
        "claim": CLAIM_WEIGHT,
        "evidence": EVIDENCE_WEIGHT,
        "entity": ENTITY_WEIGHT,
        "topic": TOPIC_WEIGHT,
    }


def test_an_unchanged_lake_costs_no_reads(lake, monkeypatch):

    put(lake, "one", seed=1)

    index = make_index(lake)
    index.articles()

    reads = []
    monkeypatch.setattr(index, "_read", lambda entry: reads.append(entry) or None)

    index.articles()
    index.articles_document()

    assert reads == []


def synthetic(n: int) -> list[MapArticle]:
    """n articles as the map holds them, without a lake: the size test's input."""

    rng = np.random.default_rng(0)
    keys = list(anchors())
    people = [Entity(key=f"person:p{i}", name=f"Person Number {i}", type="person") for i in range(n // 4)]

    articles = []

    for i in range(n):
        key = keys[i % len(keys)]
        articles.append(MapArticle(
            id=f"{i:016x}",
            record_id=f"r{i}",
            title=f"A good news story number {i} about {TOPICS[key].name.lower()} and its people",
            language="en" if i % 2 else "es",
            day=f"2026-10-{1 + i % 28:02d}",
            source=f"Outlet {i % 30}",
            verdict="TRUE",
            group=anchors()[key].group,
            topics=((key, 0.5),),
            entities=tuple(people[j % len(people)] for j in rng.integers(0, len(people), 5)),
            claims={},
            evidence=frozenset(),
            x=float(rng.uniform(-1, 1)),
            y=float(rng.uniform(-1, 1)),
            approximate=None,
            sort_at=float(i),
            vector=None,
        ))

    return articles


def test_ten_thousand_articles_serialise_fast_and_small(lake):
    """
    docs/goals.md, N1: under 200 ms and under 1 MB gzipped at 10k. CPU
    time, not wall time: in the full suite on 29 Oct, with the model
    benchmark running (load average ~21 on 14 threads), the wall clock
    failed what the same code passed alone.
    """

    index = make_index(lake)
    index.refresh = lambda: None
    index._rebuild(synthetic(10_000))

    best = float("inf")

    for attempt in range(3):
        index._payloads = {}
        started = time.process_time()
        _, body = index.payload("articles", index.articles_document, f"try{attempt}")
        best = min(best, time.process_time() - started)

    assert len(body) < 1_000_000
    assert best < 0.2
    assert json.loads(gzip.decompress(body))["count"] == 10_000
