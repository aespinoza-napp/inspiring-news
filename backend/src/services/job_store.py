import threading
from datetime import datetime
from uuid import uuid4

from src.models.core.job import Job, JobStatus, PhaseEvent
from src.services.job_journal import JobJournal
from src.services.scraper.article_stats import comparable_url

_ACTIVE = (JobStatus.QUEUED, JobStatus.RUNNING)


class JobStore:
    """
    In-memory job registry, single process only (a dict behind a lock) -
    fine for this app's single-worker dev/deploy model. Would need a
    shared store (e.g. Redis) behind multiple workers.

    With a journal attached, every change is also appended to disk as it
    happens, and `get` falls back to it for jobs this process no longer
    holds (after a restart). The journal is optional and has no default:
    without one this is exactly the in-memory store it always was.
    """

    def __init__(self, journal: JobJournal | None = None, keep_finished: int | None = None):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        # url -> job_id, for as long as that job is queued/running. Lets
        # get_or_create() dedupe two near-simultaneous requests for the
        # same URL onto one job instead of both running the full
        # pipeline (duplicate scraping/enrichment/Qdrant writes) - the
        # same shape of race container.py's singleton-construction lock
        # fixed, but for the analysis run itself rather than service
        # construction.
        self._in_flight: dict[str, str] = {}
        self._journal = journal
        # How many finished jobs stay in memory once a journal holds them
        # all; None keeps every one (Sep 21 audit: the store never evicted).
        self._keep_finished = keep_finished
        # Jobs created while a journal was attached: only these can be
        # evicted, since only these can be read back from it.
        self._journalled: set[str] = set()

    def attach_journal(self, journal: JobJournal | None, keep_finished: int | None = None) -> None:

        self._journal = journal
        self._keep_finished = keep_finished

    def create(self, url: str, kind: str = "article") -> Job:

        job = Job(job_id=uuid4().hex, url=url, kind=kind)

        with self._lock:
            self._jobs[job.job_id] = job
            if self._journal is not None:
                self._journalled.add(job.job_id)

        self._record(job.job_id, "created", url=url, kind=kind)

        return job

    def get_or_create(self, url: str) -> tuple[Job, bool]:
        """
        Returns (job, reused). If a job for this exact URL is already
        queued/running, returns it instead of starting a duplicate;
        otherwise creates and registers a new one. Both branches happen
        under one lock acquisition so two callers racing on the same URL
        cannot both observe "nothing in flight" and both create one.
        """

        # Host and path: the same article with a tracking parameter or a
        # trailing slash is the same job (Sep 21 audit).
        key = comparable_url(url)

        with self._lock:

            existing_id = self._in_flight.get(key)

            if existing_id is not None:
                existing = self._jobs.get(existing_id)
                if existing is not None:
                    return existing, True

            job = Job(job_id=uuid4().hex, url=url)
            self._jobs[job.job_id] = job
            self._in_flight[key] = job.job_id
            if self._journal is not None:
                self._journalled.add(job.job_id)

        self._record(job.job_id, "created", url=url)

        return job, False

    def get(self, job_id: str) -> Job | None:

        with self._lock:
            job = self._jobs.get(job_id)

        if job is None and self._journal is not None:
            return self._journal.load(job_id)

        return job

    def list(self, limit: int = 20) -> list[Job]:
        """
        Jobs held in memory, active ones first and then newest-first.
        Past runs from before a restart are not listed - they stay
        reachable by id through `get`.
        """

        with self._lock:
            jobs = list(self._jobs.values())

        jobs.sort(key=lambda job: job.updated_at, reverse=True)
        jobs.sort(key=lambda job: job.status not in _ACTIVE)

        return jobs[:limit]

    def add_event(self, job_id: str, phase: str, data: dict) -> None:

        with self._lock:

            job = self._jobs.get(job_id)

            if job is None:
                return

            job.events.append(PhaseEvent(phase=phase, data=data))
            job.status = JobStatus.RUNNING
            job.updated_at = datetime.now()

        self._record(job_id, "event", phase=phase, data=data)

    def complete(self, job_id: str, result: dict) -> None:

        with self._lock:

            job = self._jobs.get(job_id)

            if job is None:
                return

            job.result = result
            job.status = JobStatus.DONE
            job.updated_at = datetime.now()

            self._clear_in_flight(job)

        # Journalled before it can be evicted, so `get` always finds it.
        self._record(job_id, "result", result=result)

        with self._lock:
            self._evict()

    def fail(self, job_id: str, error: str) -> None:

        with self._lock:

            job = self._jobs.get(job_id)

            if job is None:
                return

            job.error = error
            job.status = JobStatus.FAILED
            job.updated_at = datetime.now()

            self._clear_in_flight(job)

        self._record(job_id, "error", error=error)

        with self._lock:
            self._evict()

    def _record(self, job_id: str, type_: str, **payload) -> None:
        """Outside the lock: file I/O must not stall every other job."""

        if self._journal is not None:
            self._journal.append(job_id, type_, **payload)

    def _evict(self) -> None:
        """
        Caller must hold self._lock. The oldest finished jobs beyond
        `keep_finished` leave memory - only with a journal attached, which
        has every event and the result, so `get` still answers for them
        by id; the Live screen's list (in-memory jobs only) forgets them.
        An active job is never evicted. Without a journal nothing could
        serve an evicted job, so nothing is evicted.
        """

        if self._journal is None or self._keep_finished is None:
            return

        finished = [job for job in self._jobs.values() if job.status not in _ACTIVE]

        if len(finished) <= self._keep_finished:
            return

        finished.sort(key=lambda job: job.updated_at)

        # Oldest first, journalled ones only: a job from before the
        # journal was attached stays, or it would be lost.
        excess = len(finished) - self._keep_finished
        for job in finished:
            if excess == 0:
                break
            if job.job_id in self._journalled:
                del self._jobs[job.job_id]
                self._journalled.discard(job.job_id)
                excess -= 1

    def _clear_in_flight(self, job: Job) -> None:
        """Caller must hold self._lock."""

        key = comparable_url(job.url)

        if self._in_flight.get(key) == job.job_id:
            del self._in_flight[key]
