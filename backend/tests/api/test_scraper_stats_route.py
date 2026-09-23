from fastapi.testclient import TestClient
from pydantic import SecretStr

import src.api.routes as routes
from src.config.settings import settings
from src.main import app
from src.services.scraper.request_stats import Outcome, RequestStats

client = TestClient(app)


def use_stats(monkeypatch) -> RequestStats:

    stats = RequestStats()
    monkeypatch.setattr(routes, "request_stats", stats)
    return stats


def test_the_counts_are_returned_per_domain(monkeypatch):

    stats = use_stats(monkeypatch)
    stats.record("https://a.com/1", Outcome.OK)
    stats.record("https://a.com/2", Outcome.HTTP_ERROR, status=403)

    response = client.get("/scraper/stats")

    assert response.status_code == 200

    body = response.json()
    assert body["totals"]["requests"] == 2
    assert body["domains"][0]["domain"] == "a.com"
    assert body["domains"][0]["outcomes"] == {"ok": 1, "http_error": 1}


def test_the_counts_are_behind_the_storage_key(monkeypatch):
    """They name every URL the server has been asked to read."""

    use_stats(monkeypatch)
    monkeypatch.setattr(settings, "STORAGE_API_KEY", SecretStr("secret"))

    assert client.get("/scraper/stats").status_code == 401
    assert client.get("/scraper/stats", headers={"x-api-key": "secret"}).status_code == 200


def test_scraped_articles_are_read_from_the_lake(monkeypatch):

    from tests.services.scraper.test_article_stats import FakeLake, raw

    monkeypatch.setattr(
        routes,
        "get_datalake_repository",
        lambda: FakeLake(raw=[raw("https://a.com/1")]),
    )

    response = client.get("/scraper/articles")

    assert response.status_code == 200
    assert response.json()["totals"]["scraped"] == 1
