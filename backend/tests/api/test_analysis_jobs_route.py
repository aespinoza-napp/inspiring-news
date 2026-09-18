import time

from fastapi.testclient import TestClient

import src.api.routes as routes
from src.main import app

client = TestClient(app)


def _poll_until_finished(job_id: str, timeout: float = 5.0) -> dict:
    """
    POST /analyze/jobs now runs on the bounded job queue (a real
    ThreadPoolExecutor - see src/services/job_queue.py), not
    BackgroundTasks, so the job is no longer guaranteed done by the time
    the POST response comes back. Poll instead of asserting immediately.
    """

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        body = client.get(f"/analyze/jobs/{job_id}").json()
        if body["status"] in ("done", "failed"):
            return body
        time.sleep(0.01)

    raise AssertionError(f"job {job_id} did not finish within {timeout}s")


class FakeAnalysisService:
    """
    A fast, no-network stand-in for AnalysisService - runs synchronously
    but reports phases the same way the real one does, so the route (and
    the background-task wiring) can be tested without hitting the real
    scraper/SearXNG/LLM.
    """

    def analyze(self, url, force_refresh=False, on_phase=None, thresholds=None):

        report = on_phase or (lambda phase, data: None)

        report("scraping", {"url": url})
        report("enriched", {"title": "Fake title", "keywords": ["a", "b"]})

        result = {"url": url, "title": "Fake title", "cached": False}

        report("done", result)

        return result


def test_create_and_poll_analysis_job(monkeypatch):

    monkeypatch.setattr(routes, "get_analysis_service", lambda: FakeAnalysisService())

    create_response = client.post("/analyze/jobs", json={"url": "https://example.com/a"})

    assert create_response.status_code == 202

    job_id = create_response.json()["jobId"]

    body = _poll_until_finished(job_id)

    assert body["status"] == "done"
    assert body["result"] == {"url": "https://example.com/a", "title": "Fake title", "cached": False}

    phases = [event["phase"] for event in body["events"]]
    assert phases == ["initializing", "initialized", "scraping", "enriched"]


def test_get_unknown_job_returns_404():

    response = client.get("/analyze/jobs/does-not-exist")

    assert response.status_code == 404


def test_create_job_returns_202_even_when_service_construction_fails(monkeypatch):
    """
    Regression test: building AnalysisService (which connects to Qdrant)
    used to happen eagerly in the route handler, so a construction
    failure (e.g. the local Qdrant storage lock being briefly busy) 500'd
    the POST /analyze/jobs request itself. It must now be deferred into
    the background task, so the request always succeeds (202) and the
    failure shows up as a clean job status instead.
    """

    def failing_factory():
        raise RuntimeError("Storage folder is already accessed by another instance")

    monkeypatch.setattr(routes, "get_analysis_service", failing_factory)

    create_response = client.post("/analyze/jobs", json={"url": "https://example.com/a"})

    assert create_response.status_code == 202

    job_id = create_response.json()["jobId"]

    body = _poll_until_finished(job_id)

    assert body["status"] == "failed"
    assert "already accessed" in body["error"]


def test_sync_analyze_endpoint_degrades_gracefully_when_service_unavailable(monkeypatch):

    def failing_factory():
        raise RuntimeError("Storage folder is already accessed by another instance")

    monkeypatch.setattr(routes, "get_analysis_service", failing_factory)

    response = client.post("/analyze", json={"urls": ["https://example.com/a"]})

    assert response.status_code == 200

    body = response.json()

    assert "error" in body["results"][0]
    assert body["results"][0]["url"] == "https://example.com/a"
