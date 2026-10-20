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


# ----------------------------------------------------------------------
# Eviction (Sep 21 audit: the store never evicted)
# ----------------------------------------------------------------------


def _finish(store, n, start=0):

    jobs = []
    for i in range(start, start + n):
        job = store.create(f"https://example.com/{i}")
        store.complete(job.job_id, {"i": i})
        jobs.append(job)
    return jobs


def test_finished_jobs_beyond_the_cap_leave_memory_but_answer_from_the_journal(tmp_path):

    from src.services.job_journal import JobJournal

    store = JobStore(JobJournal(tmp_path / "journal"), keep_finished=2)

    running = store.create("https://example.com/running")
    store.add_event(running.job_id, "scraping", {})

    oldest, middle, newest = _finish(store, 3)

    listed = {job.job_id for job in store.list(limit=10)}

    # The oldest finished one left memory; the active one never does.
    assert listed == {running.job_id, middle.job_id, newest.job_id}

    # Still served by id, from the journal, with its result.
    restored = store.get(oldest.job_id)
    assert restored is not None and restored.result == {"i": 0}


def test_without_a_journal_nothing_is_evicted():

    store = JobStore(keep_finished=1)

    _finish(store, 3)

    assert len(store.list(limit=10)) == 3


def test_a_job_from_before_the_journal_is_never_evicted(tmp_path):
    """It was never journalled: evicted, nothing could serve it again."""

    from src.services.job_journal import JobJournal

    store = JobStore()
    [early] = _finish(store, 1)

    store.attach_journal(JobJournal(tmp_path / "journal"), keep_finished=1)
    _finish(store, 2, start=1)

    ids = {job.job_id for job in store.list(limit=10)}

    assert early.job_id in ids
    assert store.get(early.job_id).result == {"i": 0}
