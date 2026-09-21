import threading
from datetime import datetime
from uuid import uuid4

from src.models.core.job import Job, JobStatus, PhaseEvent
from src.services.job_journal import JobJournal

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

    def __init__(self, journal: JobJournal | None = None):
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

    def attach_journal(self, journal: JobJournal | None) -> None:

        self._journal = journal

    def create(self, url: str, kind: str = "article") -> Job:

        job = Job(job_id=uuid4().hex, url=url, kind=kind)

        with self._lock:
            self._jobs[job.job_id] = job

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

        with self._lock:

            existing_id = self._in_flight.get(url)

            if existing_id is not None:
                existing = self._jobs.get(existing_id)
                if existing is not None:
                    return existing, True

            job = Job(job_id=uuid4().hex, url=url)
            self._jobs[job.job_id] = job
            self._in_flight[url] = job.job_id

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

        self._record(job_id, "result", result=result)

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

    def _record(self, job_id: str, type_: str, **payload) -> None:
        """Outside the lock: file I/O must not stall every other job."""

        if self._journal is not None:
            self._journal.append(job_id, type_, **payload)

    def _clear_in_flight(self, job: Job) -> None:
        """Caller must hold self._lock."""

        if self._in_flight.get(job.url) == job.job_id:
            del self._in_flight[job.url]
