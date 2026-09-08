from unittest.mock import Mock

from src.models.core.job import JobStatus
from src.services.job_runner import run_analysis_job
from src.services.job_store import JobStore


def make_analysis_service(side_effect=None, return_value=None) -> Mock:

    service = Mock()

    if side_effect is not None:
        service.analyze.side_effect = side_effect
    else:
        service.analyze.return_value = return_value

    return service


def test_run_analysis_job_records_phases_and_completes():

    store = JobStore()
    job = store.create("https://example.com/a")

    def fake_analyze(url, force_refresh=False, on_phase=None, thresholds=None):
        on_phase("scraping", {"url": url})
        on_phase("enriched", {"keywords": ["a"]})
        on_phase("done", {"url": url, "title": "Final"})
        return {"url": url, "title": "Final"}

    analysis_service = make_analysis_service(side_effect=fake_analyze)

    run_analysis_job(store, lambda: analysis_service, job.job_id, job.url)

    updated = store.get(job.job_id)

    assert updated.status == JobStatus.DONE
    assert updated.result == {"url": job.url, "title": "Final"}
    assert [event.phase for event in updated.events] == [
        "initializing", "initialized", "scraping", "enriched",
    ]


def test_run_analysis_job_reports_initializing_before_building_the_service():
    """
    Regression test: building AnalysisService (loading GLiNER/embedding/
    sentiment models on the first request in a fresh process) can take
    ~10-15s with no on_phase events firing during it - "initializing"
    must be recorded before get_analysis_service() is even called, or a
    polling client sees nothing but status "queued" for that whole
    window, indistinguishable from being stuck.
    """

    store = JobStore()
    job = store.create("https://example.com/a")

    call_order = []

    def factory():
        call_order.append("factory")
        return make_analysis_service(return_value={"url": job.url})

    run_analysis_job(store, factory, job.job_id, job.url)

    updated = store.get(job.job_id)

    phases = [event.phase for event in updated.events]
    assert phases[:2] == ["initializing", "initialized"]
    assert call_order == ["factory"]


def test_run_analysis_job_records_failure_from_failed_phase():

    store = JobStore()
    job = store.create("https://example.com/a")

    def fake_analyze(url, force_refresh=False, on_phase=None, thresholds=None):
        on_phase("scraping", {"url": url})
        on_phase("failed", {"url": url, "error": "Could not extract content"})
        return {"url": url, "error": "Could not extract content"}

    analysis_service = make_analysis_service(side_effect=fake_analyze)

    run_analysis_job(store, lambda: analysis_service, job.job_id, job.url)

    updated = store.get(job.job_id)

    assert updated.status == JobStatus.FAILED
    assert updated.error == "Could not extract content"


def test_run_analysis_job_records_failure_on_unexpected_exception():

    store = JobStore()
    job = store.create("https://example.com/a")

    analysis_service = make_analysis_service(side_effect=RuntimeError("unexpected boom"))

    run_analysis_job(store, lambda: analysis_service, job.job_id, job.url)

    updated = store.get(job.job_id)

    assert updated.status == JobStatus.FAILED
    assert "unexpected boom" in updated.error


def test_run_analysis_job_records_failure_when_service_construction_fails():
    """
    The regression this guards against: get_analysis_service() (building
    AnalysisService, which connects to Qdrant) must happen inside this
    function's try/except, not before it's called - otherwise a
    construction failure (e.g. Qdrant's storage lock busy) escapes as an
    unhandled exception in the caller instead of landing here as a clean
    job failure.
    """

    store = JobStore()
    job = store.create("https://example.com/a")

    def failing_factory():
        raise RuntimeError("Storage folder is already accessed by another instance")

    run_analysis_job(store, failing_factory, job.job_id, job.url)

    updated = store.get(job.job_id)

    assert updated.status == JobStatus.FAILED
    assert "already accessed" in updated.error


def test_run_analysis_job_passes_force_refresh_through():

    store = JobStore()
    job = store.create("https://example.com/a")

    analysis_service = make_analysis_service(return_value={"url": job.url})

    run_analysis_job(store, lambda: analysis_service, job.job_id, job.url, force_refresh=True)

    analysis_service.analyze.assert_called_once()
    _, kwargs = analysis_service.analyze.call_args
    assert kwargs["force_refresh"] is True


def test_run_analysis_job_only_builds_service_once():

    store = JobStore()
    job = store.create("https://example.com/a")

    analysis_service = make_analysis_service(return_value={"url": job.url})
    factory = Mock(return_value=analysis_service)

    run_analysis_job(store, factory, job.job_id, job.url)

    factory.assert_called_once()
