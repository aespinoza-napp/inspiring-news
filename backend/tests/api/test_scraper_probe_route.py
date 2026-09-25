from fastapi.testclient import TestClient
from pydantic import SecretStr

import src.api.routes as routes
from src.config.settings import settings
from src.main import app
from src.services.scraper.request_stats import RequestStats
from src.services.scraper.source_probe import SourceProbe

from tests.builders.source_builder import build_source
from tests.services.scraper.test_source_probe import FakeFeeds, FakeTopicPages

client = TestClient(app)


class StartsNothing(SourceProbe):
    """Records the start instead of launching a thread against real sites."""

    started = None

    def start(self, source_ids=None, per_source=5):
        if self._running:
            return False
        self.started = (source_ids, per_source)
        self._running = True
        return True


def use_probe(monkeypatch, **kwargs) -> StartsNothing:

    probe = StartsNothing(
        sources=[build_source(id="bbc"), build_source(id="rtve")],
        stats=RequestStats(),
        feed_discovery=FakeFeeds({}),
        topic_pages=FakeTopicPages({}),
        **kwargs,
    )

    monkeypatch.setattr(routes, "get_source_probe", lambda: probe)

    return probe


def test_a_probe_is_started_and_its_state_returned(monkeypatch):

    probe = use_probe(monkeypatch)

    response = client.post("/scraper/probe", json={"sources": ["rtve"], "perSource": 3})

    assert response.status_code == 202
    assert response.json()["running"] is True
    assert probe.started == (["rtve"], 3)


def test_a_second_probe_while_one_runs_is_refused(monkeypatch):

    use_probe(monkeypatch)

    client.post("/scraper/probe", json={})

    assert client.post("/scraper/probe", json={}).status_code == 409


def test_an_unknown_source_is_refused_before_anything_starts(monkeypatch):

    probe = use_probe(monkeypatch)

    response = client.post("/scraper/probe", json={"sources": ["nope"]})

    assert response.status_code == 422
    assert probe.started is None


def test_per_source_is_capped(monkeypatch):

    use_probe(monkeypatch)

    assert client.post("/scraper/probe", json={"perSource": 500}).status_code == 422


def test_the_last_report_is_returned(monkeypatch):

    probe = use_probe(monkeypatch)
    probe.last_report = {"totals": {"sources": 2}}

    body = client.get("/scraper/probe").json()

    assert body["running"] is False
    assert body["report"] == {"totals": {"sources": 2}}


def test_the_probe_is_behind_the_storage_key(monkeypatch):
    """One call sends requests to every configured site."""

    use_probe(monkeypatch)
    monkeypatch.setattr(settings, "STORAGE_API_KEY", SecretStr("secret"))

    assert client.get("/scraper/probe").status_code == 401
    assert client.post("/scraper/probe", json={}).status_code == 401
    assert client.get("/scraper/probe", headers={"x-api-key": "secret"}).status_code == 200
