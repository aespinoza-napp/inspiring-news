from fastapi.testclient import TestClient

import src.api.routes as routes
from src.main import app

client = TestClient(app)


class FakeAnalysisService:
    """
    A fast, no-network stand-in for AnalysisService - runs synchronously
    but reports phases the same way the real one does, so the route (and
    the background-task wiring) can be tested without hitting the real
    scraper/SearXNG/LLM.
    """

    def analyze(self, url, force_refresh=False, on_phase=None):

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

    status_response = client.get(f"/analyze/jobs/{job_id}")

    assert status_response.status_code == 200

    body = status_response.json()

    assert body["status"] == "done"
    assert body["result"] == {"url": "https://example.com/a", "title": "Fake title", "cached": False}

    phases = [event["phase"] for event in body["events"]]
    assert phases == ["scraping", "enriched"]


def test_get_unknown_job_returns_404():

    response = client.get("/analyze/jobs/does-not-exist")

    assert response.status_code == 404
