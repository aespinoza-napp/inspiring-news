import json
from datetime import datetime

from src.models.core.job import JobStatus
from src.services.job_journal import JobJournal
from src.services.job_store import JobStore


def test_a_job_is_rebuilt_from_its_journal_after_a_restart(tmp_path):

    journal = JobJournal(tmp_path)

    first_process = JobStore(journal=journal)

    job = first_process.create("https://example.com/a")
    first_process.add_event(job.job_id, "searching_web", {"queries": ["nasa water"]})
    first_process.add_event(job.job_id, "web_results", {"results": [{"url": "https://x.com"}]})
    first_process.complete(job.job_id, {"title": "Done"})

    second_process = JobStore(journal=journal)

    restored = second_process.get(job.job_id)

    assert restored is not None
    assert restored.url == "https://example.com/a"
    assert restored.status == JobStatus.DONE
    assert restored.result == {"title": "Done"}
    assert [event.phase for event in restored.events] == ["searching_web", "web_results"]
    assert restored.events[0].data == {"queries": ["nasa water"]}


def test_a_run_that_died_midway_keeps_everything_up_to_that_point(tmp_path):

    journal = JobJournal(tmp_path)

    store = JobStore(journal=journal)

    job = store.create("https://example.com/a")
    store.add_event(job.job_id, "searching_web", {"queries": ["q"]})
    # No complete() or fail(): the process was killed here.

    restored = JobStore(journal=journal).get(job.job_id)

    assert restored.status == JobStatus.FAILED
    assert "Interrupted" in restored.error
    assert [event.phase for event in restored.events] == ["searching_web"]


def test_a_failure_is_journalled(tmp_path):

    store = JobStore(journal=JobJournal(tmp_path))

    job = store.create("https://example.com/a")
    store.fail(job.job_id, "boom")

    restored = JobStore(journal=JobJournal(tmp_path)).get(job.job_id)

    assert restored.status == JobStatus.FAILED
    assert restored.error == "boom"


def test_a_claim_job_keeps_its_kind(tmp_path):

    store = JobStore(journal=JobJournal(tmp_path))

    job = store.create("Water exists on Mars.", kind="claim")

    restored = JobStore(journal=JobJournal(tmp_path)).get(job.job_id)

    assert restored.kind == "claim"


def test_memory_wins_over_the_journal_for_a_live_job(tmp_path):

    store = JobStore(journal=JobJournal(tmp_path))

    job = store.create("https://example.com/a")
    store.add_event(job.job_id, "scraping", {})

    assert store.get(job.job_id) is job
    assert store.get(job.job_id).status == JobStatus.RUNNING


def test_an_id_that_is_not_a_job_id_never_touches_the_disk(tmp_path):
    """
    GET /analyze/jobs/{id} takes the id from the client and falls back to
    reading a file. Only exactly what this app generates may reach a path.
    """

    outside = tmp_path / "secret.jsonl"
    outside.write_text(json.dumps({"type": "created", "url": "leaked"}) + "\n")

    journal = JobJournal(tmp_path / "journal")
    journal.directory.mkdir()

    for hostile in ("../secret", "..\\secret", "/etc/passwd", "a" * 31, "A" * 32, ""):
        assert journal.load(hostile) is None

    journal.append("../secret", "event", phase="x", data={})

    assert "phase" not in outside.read_text()


def test_a_torn_last_line_does_not_lose_the_rest(tmp_path):

    journal = JobJournal(tmp_path)

    store = JobStore(journal=journal)

    job = store.create("https://example.com/a")
    store.add_event(job.job_id, "scraping", {})

    with (tmp_path / f"{job.job_id}.jsonl").open("a", encoding="utf-8") as handle:
        handle.write('{"at": "2026-01-01T00:00:00", "type": "ev')

    restored = JobStore(journal=journal).get(job.job_id)

    assert [event.phase for event in restored.events] == ["scraping"]


def test_an_unwritable_journal_never_breaks_the_job(tmp_path):
    """The journal records the analysis; it must not be able to stop it."""

    blocker = tmp_path / "not-a-directory"
    blocker.write_text("a file where the directory should be")

    store = JobStore(journal=JobJournal(blocker / "journal"))

    job = store.create("https://example.com/a")
    store.add_event(job.job_id, "scraping", {})
    store.complete(job.job_id, {"title": "still fine"})

    assert store.get(job.job_id).status == JobStatus.DONE


def test_nothing_is_created_until_the_first_write(tmp_path):

    directory = tmp_path / "journal"

    JobJournal(directory)

    assert not directory.exists()


def test_list_puts_active_jobs_first_then_newest(tmp_path):

    store = JobStore()

    old_done = store.create("https://example.com/old")
    store.complete(old_done.job_id, {})

    running = store.create("https://example.com/running")
    store.add_event(running.job_id, "scraping", {})

    new_done = store.create("https://example.com/new")
    store.complete(new_done.job_id, {})

    # Explicit, not left to the clock: Windows timestamps can tie.
    old_done.updated_at = datetime(2026, 1, 1)
    new_done.updated_at = datetime(2026, 1, 2)
    running.updated_at = datetime(2025, 1, 1)

    urls = [job.url for job in store.list()]

    assert urls == [
        "https://example.com/running",
        "https://example.com/new",
        "https://example.com/old",
    ]


def test_list_respects_the_limit():

    store = JobStore()

    for index in range(5):
        store.create(f"https://example.com/{index}")

    assert len(store.list(limit=2)) == 2
