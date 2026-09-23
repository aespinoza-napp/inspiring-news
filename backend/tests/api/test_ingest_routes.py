from fastapi.testclient import TestClient

import src.api.routes as routes
from src.main import app

from tests.builders.source_builder import build_source

client = TestClient(app)


class FakeIngestion:

    def __init__(self):
        self.calls = []
        self.last_run = None

    def enabled_sources(self):
        return [build_source(id="bbc", name="BBC"), build_source(id="nasa", name="NASA")]

    def run(self, start_job, source_ids=None, per_source=3):
        self.calls.append((source_ids, per_source))
        job_id, _ = start_job("https://bbc.com/a")
        return {"sources": [], "totals": {"queued": 1}, "jobId": job_id}


def use_ingestion(monkeypatch):

    service = FakeIngestion()
    started = []

    monkeypatch.setattr(routes, "get_ingestion_service", lambda: service)
    monkeypatch.setattr(
        routes,
        "_start_job",
        lambda url, force, thresholds, purpose="article": (
            started.append((url, purpose)) or ("job-1", False)
        ),
    )

    return service, started


def test_ingest_queues_jobs_marked_as_ingestion(monkeypatch):
    """The purpose is what separates discovered articles in the scraper stats."""

    service, started = use_ingestion(monkeypatch)

    response = client.post("/ingest", json={"sources": ["nasa"], "perSource": 2})

    assert response.status_code == 200
    assert service.calls == [(["nasa"], 2)]
    assert started == [("https://bbc.com/a", "ingestion")]


def test_an_unknown_source_is_rejected_before_anything_runs(monkeypatch):

    service, _ = use_ingestion(monkeypatch)

    response = client.post("/ingest", json={"sources": ["nope"]})

    assert response.status_code == 422
    assert service.calls == []


def test_per_source_is_bounded(monkeypatch):
    """Each queued article is a full analysis; one call must not start hundreds."""

    use_ingestion(monkeypatch)

    assert client.post("/ingest", json={"perSource": 500}).status_code == 422


def test_the_sources_and_last_run_are_listed(monkeypatch):

    use_ingestion(monkeypatch)

    body = client.get("/ingest/sources").json()

    assert [source["id"] for source in body["sources"]] == ["bbc", "nasa"]
    assert body["lastRun"] is None
