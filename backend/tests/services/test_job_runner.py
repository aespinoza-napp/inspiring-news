from unittest.mock import Mock

from src.models.core.job import JobStatus
from src.services.job_runner import run_analysis_job
from src.services.job_store import JobStore


def test_run_analysis_job_records_phases_and_completes():

    store = JobStore()
    job = store.create("https://example.com/a")

    analysis_service = Mock()

    def fake_analyze(url, force_refresh=False, on_phase=None):
        on_phase("scraping", {"url": url})
        on_phase("enriched", {"keywords": ["a"]})
        on_phase("done", {"url": url, "title": "Final"})
        return {"url": url, "title": "Final"}

    analysis_service.analyze.side_effect = fake_analyze

    run_analysis_job(store, analysis_service, job.job_id, job.url)

    updated = store.get(job.job_id)

    assert updated.status == JobStatus.DONE
    assert updated.result == {"url": job.url, "title": "Final"}
    assert [event.phase for event in updated.events] == ["scraping", "enriched"]


def test_run_analysis_job_records_failure_from_failed_phase():

    store = JobStore()
    job = store.create("https://example.com/a")

    analysis_service = Mock()

    def fake_analyze(url, force_refresh=False, on_phase=None):
        on_phase("scraping", {"url": url})
        on_phase("failed", {"url": url, "error": "Could not extract content"})
        return {"url": url, "error": "Could not extract content"}

    analysis_service.analyze.side_effect = fake_analyze

    run_analysis_job(store, analysis_service, job.job_id, job.url)

    updated = store.get(job.job_id)

    assert updated.status == JobStatus.FAILED
    assert updated.error == "Could not extract content"


def test_run_analysis_job_records_failure_on_unexpected_exception():

    store = JobStore()
    job = store.create("https://example.com/a")

    analysis_service = Mock()
    analysis_service.analyze.side_effect = RuntimeError("unexpected boom")

    run_analysis_job(store, analysis_service, job.job_id, job.url)

    updated = store.get(job.job_id)

    assert updated.status == JobStatus.FAILED
    assert "unexpected boom" in updated.error


def test_run_analysis_job_passes_force_refresh_through():

    store = JobStore()
    job = store.create("https://example.com/a")

    analysis_service = Mock()
    analysis_service.analyze.return_value = {"url": job.url}

    run_analysis_job(store, analysis_service, job.job_id, job.url, force_refresh=True)

    analysis_service.analyze.assert_called_once()
    _, kwargs = analysis_service.analyze.call_args
    assert kwargs["force_refresh"] is True
