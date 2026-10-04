from fastapi.testclient import TestClient
from pydantic import SecretStr

import src.api.routes as routes
from src.config.settings import settings
from src.main import app
from src.services.reader.index import ReaderIndex

from tests.services.reader.reader_lake import make_lake, publish

client = TestClient(app)


def use_index(monkeypatch, tmp_path) -> ReaderIndex:
    """A reader over a throwaway lake, so nothing reads the real one."""

    index = ReaderIndex(make_lake(tmp_path))
    monkeypatch.setattr(routes, "get_reader_index", lambda: index)
    return index


def test_the_feed_lists_published_articles_with_the_lake_counts(monkeypatch, tmp_path):

    index = use_index(monkeypatch, tmp_path)
    publish(index.lake, "https://a.example/one-published-story-here", topic="Climate")

    response = client.get("/reader/articles", params={"topic": "climate", "limit": 5})

    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 1
    assert body["limit"] == 5
    assert body["lake"] == {"analysed": 1, "publishable": 1}


def test_an_article_is_found_by_the_id_its_card_carries(monkeypatch, tmp_path):

    index = use_index(monkeypatch, tmp_path)
    publish(index.lake)

    article_id = client.get("/reader/articles").json()["items"][0]["id"]

    response = client.get(f"/reader/articles/{article_id}")

    assert response.status_code == 200
    assert response.json()["claims"][0]["outcome"] == "judged"


def test_an_unknown_article_is_404_and_a_malformed_id_never_reaches_the_lake(monkeypatch, tmp_path):

    use_index(monkeypatch, tmp_path)

    assert client.get(f"/reader/articles/{'0' * 16}").status_code == 404
    assert client.get("/reader/articles/..%2F..%2Fsecrets").status_code in (404, 422)
    assert client.get("/reader/articles/NOT-A-HEX-ID-123").status_code == 422


def test_a_page_is_capped(monkeypatch, tmp_path):

    use_index(monkeypatch, tmp_path)

    assert client.get("/reader/articles", params={"limit": 51}).status_code == 422
    assert client.get("/reader/articles", params={"offset": -1}).status_code == 422


def test_the_reader_is_open_even_when_the_storage_key_is_set(monkeypatch, tmp_path):
    """
    On purpose: it shows what the public reader page shows anyone. A key
    the frontend attaches for every visitor would protect nothing.
    """

    use_index(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "STORAGE_API_KEY", SecretStr("secret"))

    assert client.get("/reader/articles").status_code == 200
