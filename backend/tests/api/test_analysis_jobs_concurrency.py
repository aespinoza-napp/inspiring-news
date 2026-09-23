import threading
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

import src.api.routes as routes
import src.container as container
from src.config.settings import settings
from src.main import app

client = TestClient(app)


def _reset_job_queue():
    setattr(container, "_job_queue", None)


def _poll_until_finished(job_id: str, timeout: float = 5.0) -> dict:

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        body = client.get(f"/analyze/jobs/{job_id}").json()
        if body["status"] in ("done", "failed"):
            return body
        time.sleep(0.01)

    raise AssertionError(f"job {job_id} did not finish within {timeout}s")


def _make_tracking_service(call_log: list[str], hold_seconds: float = 0.05):
    """
    A fake AnalysisService whose analyze() records how many calls are
    concurrently inside it (for the concurrency-cap assertion) and which
    URL each call was made for (for the no-cross-contamination and
    dedup assertions), without touching any real network/model service.
    """

    active = {"n": 0, "max": 0}
    active_lock = threading.Lock()

    class TrackingAnalysisService:
        def analyze(self, url, force_refresh=False, on_phase=None, thresholds=None, purpose="article"):

            report = on_phase or (lambda phase, data: None)

            with active_lock:
                active["n"] += 1
                active["max"] = max(active["max"], active["n"])

            call_log.append(url)
            report("scraping", {"url": url})
            time.sleep(hold_seconds)  # widen the concurrency window

            with active_lock:
                active["n"] -= 1

            result = {"url": url, "title": f"Title for {url}", "cached": False}
            report("done", result)
            return result

    return TrackingAnalysisService(), active


def test_parallel_analyze_jobs_are_bounded_by_max_concurrency(monkeypatch):
    """
    POST /analyze/jobs used to run each job on FastAPI's BackgroundTasks
    threadpool with no cap at all - N near-simultaneous POSTs meant N
    concurrent pipeline runs. It now goes through the bounded job queue
    (src/services/job_queue.py); this fires more parallel requests than
    the configured cap and asserts the observed concurrent-in-flight
    count never exceeds it.
    """

    monkeypatch.setattr(settings, "ANALYSIS_MAX_CONCURRENCY", 2)
    _reset_job_queue()

    call_log: list[str] = []
    service, active = _make_tracking_service(call_log, hold_seconds=0.1)
    monkeypatch.setattr(routes, "get_analysis_service", lambda: service)

    urls = [f"https://example.com/{i}" for i in range(6)]

    with ThreadPoolExecutor(max_workers=len(urls)) as pool:
        responses = list(
            pool.map(
                lambda url: client.post("/analyze/jobs", json={"url": url}),
                urls,
            )
        )

    for response in responses:
        assert response.status_code == 202

    job_ids = [response.json()["jobId"] for response in responses]
    bodies = [_poll_until_finished(job_id) for job_id in job_ids]

    # No cross-job contamination: each job's own result matches its own URL.
    for url, body in zip(urls, bodies):
        assert body["status"] == "done"
        assert body["result"]["url"] == url

    assert sorted(call_log) == sorted(urls)
    assert active["max"] <= settings.ANALYSIS_MAX_CONCURRENCY

    _reset_job_queue()


def test_concurrent_requests_for_the_same_url_are_deduped_onto_one_job(monkeypatch):
    """
    Regression test for the analysis-run equivalent of the
    singleton-construction race documented in docs/decisions/incidents.md:
    two /analyze/jobs requests for the identical URL, fired as close
    together as possible, must not both run the full pipeline. They
    should land on the same job id and analyze() should run exactly once
    for that URL.
    """

    monkeypatch.setattr(settings, "ANALYSIS_MAX_CONCURRENCY", 4)
    _reset_job_queue()

    call_log: list[str] = []
    service, _ = _make_tracking_service(call_log, hold_seconds=0.1)
    monkeypatch.setattr(routes, "get_analysis_service", lambda: service)

    url = "https://example.com/duplicate"

    start_barrier = threading.Barrier(2)

    def post():
        start_barrier.wait()
        return client.post("/analyze/jobs", json={"url": url})

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: post(), range(2)))

    for response in responses:
        assert response.status_code == 202

    job_ids = {response.json()["jobId"] for response in responses}
    assert len(job_ids) == 1, "both requests for the same URL should reuse one job id"

    job_id = job_ids.pop()
    body = _poll_until_finished(job_id)

    assert body["status"] == "done"
    assert call_log == [url], "analyze() must run exactly once for the deduped URL"

    _reset_job_queue()


def test_batch_endpoint_dedupes_a_repeated_url_within_the_same_request(monkeypatch):

    monkeypatch.setattr(settings, "ANALYSIS_MAX_CONCURRENCY", 4)
    _reset_job_queue()

    call_log: list[str] = []
    service, _ = _make_tracking_service(call_log, hold_seconds=0.05)
    monkeypatch.setattr(routes, "get_analysis_service", lambda: service)

    urls = [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/a",  # duplicate within the batch
    ]

    response = client.post("/analyze/jobs/batch", json={"urls": urls})

    assert response.status_code == 202

    jobs = response.json()["jobs"]
    assert [entry["url"] for entry in jobs] == urls
    assert jobs[0]["jobId"] == jobs[2]["jobId"]
    assert jobs[0]["jobId"] != jobs[1]["jobId"]

    for job_id in {entry["jobId"] for entry in jobs}:
        _poll_until_finished(job_id)

    assert sorted(call_log) == sorted(set(urls))

    batch_status = client.get(
        "/analyze/jobs/batch", params={"ids": ",".join(entry["jobId"] for entry in jobs)}
    )
    assert batch_status.status_code == 200
    statuses = [entry["status"] for entry in batch_status.json()["jobs"]]
    assert statuses == ["done", "done", "done"]

    _reset_job_queue()
