import gzip
import json

import numpy as np
from fastapi.testclient import TestClient
from pydantic import SecretStr

import src.api.map_routes as map_routes
from src.config.settings import settings
from src.config.topics import TOPICS
from src.main import app
from src.services.news_map.index import MapIndex
from src.services.reader.index import ReaderIndex
from src.services.reader.views import SourceNames

from tests.services.reader.reader_lake import make_lake, publish

client = TestClient(app)


def use_index(monkeypatch, tmp_path) -> MapIndex:
    """A map over a throwaway lake, so nothing reads the real one."""

    lake = make_lake(tmp_path)
    index = MapIndex(lake, ReaderIndex(lake), SourceNames())
    monkeypatch.setattr(map_routes, "get_map_index", lambda: index)
    return index


def put(index: MapIndex, slug: str, topic: str = "climate", seed: int = 0, **kwargs):
    vector = np.random.default_rng(seed).standard_normal(1024)
    return publish(
        index.lake,
        f"https://www.bbc.com/news/{slug}-a-story-long-enough-to-title",
        topics=[(TOPICS[topic].name, 0.6)],
        embedding=list(vector / np.linalg.norm(vector)),
        **kwargs,
    )


def test_the_map_comes_gzipped_with_its_frame(monkeypatch, tmp_path):

    index = use_index(monkeypatch, tmp_path)
    put(index, "one")

    response = client.get("/map/articles")

    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"

    body = response.json()
    assert body["count"] == 1
    assert len(body["topics"]) == len(TOPICS)


def test_an_unchanged_map_is_a_304(monkeypatch, tmp_path):

    index = use_index(monkeypatch, tmp_path)
    put(index, "one")

    tag = client.get("/map/articles").headers["etag"]

    assert client.get("/map/articles", headers={"If-None-Match": tag}).status_code == 304

    put(index, "two", topic="space", seed=1)

    changed = client.get("/map/articles", headers={"If-None-Match": tag})
    assert changed.status_code == 200
    assert changed.json()["count"] == 2


def test_a_client_without_gzip_gets_plain_json(monkeypatch, tmp_path):

    index = use_index(monkeypatch, tmp_path)
    put(index, "one")

    tag, body = index.payload("articles", index.articles_document, "")
    plain = map_routes._send(tag, body, None, "identity")

    assert "content-encoding" not in plain.headers
    assert json.loads(plain.body)["count"] == 1
    assert json.loads(gzip.decompress(body))["count"] == 1


def test_a_day_must_be_a_date(monkeypatch, tmp_path):

    use_index(monkeypatch, tmp_path)

    assert client.get("/map/articles", params={"day": "2026-10-29"}).status_code == 200
    assert client.get("/map/articles", params={"day": "yesterday"}).status_code == 422


def test_links_of_an_unknown_article_are_404_and_a_malformed_id_never_reaches_the_lake(monkeypatch, tmp_path):

    use_index(monkeypatch, tmp_path)

    assert client.get(f"/map/articles/{'0' * 16}/links").status_code == 404
    assert client.get("/map/articles/NOT-A-HEX-ID-123/links").status_code == 422


def test_an_articles_links_name_its_topics(monkeypatch, tmp_path):

    index = use_index(monkeypatch, tmp_path)
    put(index, "one")

    article_id = client.get("/map/articles").json()["articles"]["id"][0]

    links = client.get(f"/map/articles/{article_id}/links").json()

    assert links["topics"][0]["key"] == "climate"


def test_the_map_is_open_even_when_the_storage_key_is_set(monkeypatch, tmp_path):

    use_index(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "STORAGE_API_KEY", SecretStr("secret"))

    assert client.get("/map/articles").status_code == 200
    assert client.get("/map/entities").status_code == 200


def use_search(monkeypatch, index: MapIndex):
    from src.services.news_map.search import MapSearch

    search = MapSearch(index)
    monkeypatch.setattr(map_routes, "get_map_search", lambda: search)
    return search


def test_search_answers_by_name_and_word_and_says_meaning_was_skipped(monkeypatch, tmp_path):

    index = use_index(monkeypatch, tmp_path)
    use_search(monkeypatch, index)
    put(index, "one")

    body = client.get("/map/search", params={"q": "volunteers", "semantic": "false"}).json()

    assert body["semantic"] == "skipped"
    assert body["results"][0]["kind"] == "article"


def test_a_search_past_200_characters_is_422(monkeypatch, tmp_path):

    index = use_index(monkeypatch, tmp_path)
    use_search(monkeypatch, index)

    assert client.get("/map/search", params={"q": "x" * 201}).status_code == 422


def test_too_many_searches_is_a_429_with_retry_after_per_visitor(monkeypatch, tmp_path):

    index = use_index(monkeypatch, tmp_path)
    search = use_search(monkeypatch, index)
    search.semantic_limit.limit = 2

    one = {"X-Forwarded-For": "203.0.113.7, 10.0.0.2"}
    other = {"X-Forwarded-For": "198.51.100.1"}

    assert client.get("/map/search", params={"q": "a"}, headers=one).status_code == 200
    assert client.get("/map/search", params={"q": "b"}, headers=one).status_code == 200

    refused = client.get("/map/search", params={"q": "c"}, headers=one)
    assert refused.status_code == 429
    assert int(refused.headers["retry-after"]) >= 1

    # Behind the same proxy, another visitor still gets through.
    assert client.get("/map/search", params={"q": "c"}, headers=other).status_code == 200


def test_for_you_ranks_what_it_is_sent_and_is_limited_per_visitor(monkeypatch, tmp_path):

    index = use_index(monkeypatch, tmp_path)
    put(index, "one")
    put(index, "two", topic="space", seed=1)
    monkeypatch.setattr(map_routes, "_for_you_limit", map_routes.RateLimiter(2))

    body = {"interests": [{"kind": "topic", "key": "space"}]}
    first = client.post("/map/for-you", json=body, headers={"X-Forwarded-For": "203.0.113.9"})

    assert first.status_code == 200
    assert first.json()["items"][0]["reasons"][0].startswith("you follow")
    assert client.post("/map/for-you", json=body, headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 200
    assert client.post("/map/for-you", json=body, headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 429
    assert client.post("/map/for-you", json={"interests": [{"kind": "topic", "key": "x"}] * 201}).status_code == 422
