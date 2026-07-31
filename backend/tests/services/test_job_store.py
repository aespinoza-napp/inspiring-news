from src.models.core.job import JobStatus
from src.services.job_store import JobStore


def test_create_returns_queued_job():

    store = JobStore()

    job = store.create("https://example.com/a")

    assert job.status == JobStatus.QUEUED
    assert job.url == "https://example.com/a"
    assert job.events == []


def test_get_returns_none_for_unknown_job():

    store = JobStore()

    assert store.get("does-not-exist") is None


def test_add_event_appends_and_marks_running():

    store = JobStore()

    job = store.create("https://example.com/a")

    store.add_event(job.job_id, "scraping", {"url": job.url})

    updated = store.get(job.job_id)

    assert updated.status == JobStatus.RUNNING
    assert [event.phase for event in updated.events] == ["scraping"]
    assert updated.events[0].data == {"url": job.url}


def test_complete_sets_result_and_done_status():

    store = JobStore()

    job = store.create("https://example.com/a")

    store.add_event(job.job_id, "scraping", {})
    store.complete(job.job_id, {"title": "Done article"})

    updated = store.get(job.job_id)

    assert updated.status == JobStatus.DONE
    assert updated.result == {"title": "Done article"}


def test_fail_sets_error_and_failed_status():

    store = JobStore()

    job = store.create("https://example.com/a")

    store.fail(job.job_id, "boom")

    updated = store.get(job.job_id)

    assert updated.status == JobStatus.FAILED
    assert updated.error == "boom"


def test_operations_on_unknown_job_id_are_noops():

    store = JobStore()

    # None of these should raise even though the job doesn't exist.
    store.add_event("missing", "scraping", {})
    store.complete("missing", {})
    store.fail("missing", "boom")

    assert store.get("missing") is None
