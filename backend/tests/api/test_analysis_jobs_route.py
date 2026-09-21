import time

from fastapi.testclient import TestClient

import src.api.routes as routes
from src.main import app
from src.models.core.job import JobStatus

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


def test_the_live_list_shows_active_jobs_in_full_and_finished_ones_as_a_summary(monkeypatch):

    from src.services.job_store import JobStore

    store = JobStore()
    monkeypatch.setattr(routes, "job_store", store)

    running = store.create("https://example.com/running")
    store.add_event(running.job_id, "searching_web", {"claim": "c", "queries": ["q"]})

    finished = store.create("https://example.com/finished")
    store.add_event(finished.job_id, "scraping", {})
    store.complete(finished.job_id, {"title": "Done"})

    body = client.get("/analyze/jobs").json()

    assert [job["url"] for job in body["jobs"]] == [
        "https://example.com/running",
        "https://example.com/finished",
    ]

    live, done = body["jobs"]

    assert live["status"] == "running"
    assert [event["phase"] for event in live["events"]] == ["searching_web"]
    assert live["events"][0]["data"]["queries"] == ["q"]

    assert done["status"] == "done"
    assert done["events"] == []
    assert done["eventCount"] == 1
    # The whole analysis is fetched by id; shipping it for every finished
    # job on every poll would defeat leaving the events out.
    assert done["result"] is None
    assert client.get(f"/analyze/jobs/{finished.job_id}").json()["result"] == {"title": "Done"}


def test_the_live_list_rejects_an_out_of_range_limit():

    assert client.get("/analyze/jobs?limit=0").status_code == 422
    assert client.get("/analyze/jobs?limit=1000").status_code == 422


def test_a_claim_check_is_visible_as_a_job_while_it_runs(monkeypatch):

    from src.services.job_store import JobStore

    store = JobStore()
    monkeypatch.setattr(routes, "job_store", store)

    seen_while_running = []

    class FakeClaimService:

        def verify(self, text, on_phase=None, thresholds=None):

            on_phase("searching_web", {"claim": text, "queries": ["q"]})

            # Snapshot the values: list() returns the live Job objects,
            # which are mutated to DONE once this call returns.
            seen_while_running.extend(
                (job.kind, job.url, job.status) for job in store.list()
            )

            result = {"claim": text, "verdict": "TRUE"}
            on_phase("done", result)

            return result

    monkeypatch.setattr(routes, "get_claim_service", lambda: FakeClaimService())

    response = client.post("/verify-claim", json={"claim": "Water exists on Mars."})

    assert response.status_code == 200
    assert response.json() == {"claim": "Water exists on Mars.", "verdict": "TRUE"}

    assert seen_while_running == [
        ("claim", "Water exists on Mars.", JobStatus.RUNNING)
    ]

    [job] = store.list()
    assert job.status == JobStatus.DONE
    assert job.result == {"claim": "Water exists on Mars.", "verdict": "TRUE"}


def test_a_claim_check_that_raises_is_marked_failed(monkeypatch):

    from fastapi.testclient import TestClient

    from src.services.job_store import JobStore

    store = JobStore()
    monkeypatch.setattr(routes, "job_store", store)

    class ExplodingClaimService:

        def verify(self, text, on_phase=None, thresholds=None):
            raise RuntimeError("the model fell over")

    monkeypatch.setattr(routes, "get_claim_service", lambda: ExplodingClaimService())

    quiet = TestClient(app, raise_server_exceptions=False)

    assert quiet.post("/verify-claim", json={"claim": "x"}).status_code == 500

    [job] = store.list()
    assert job.status == JobStatus.FAILED
    assert "fell over" in job.error


def test_the_live_list_needs_the_storage_key_when_one_is_set(monkeypatch):
    """
    It lists every job id, with the URLs and claims behind them; ids alone
    used to be unguessable. Open when no key is configured, like /storage/*.
    """

    from pydantic import SecretStr

    from src.config.settings import settings

    monkeypatch.setattr(settings, "STORAGE_API_KEY", SecretStr("s3cret"))

    assert client.get("/analyze/jobs").status_code == 401
    assert client.get("/analyze/jobs", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/analyze/jobs", headers={"X-API-Key": "s3cret"}).status_code == 200

    monkeypatch.setattr(settings, "STORAGE_API_KEY", None)

    assert client.get("/analyze/jobs").status_code == 200
