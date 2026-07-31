import threading
from datetime import datetime
from uuid import uuid4

from src.models.core.job import Job, JobStatus, PhaseEvent


class JobStore:
    """
    In-memory job registry, single process only (a dict behind a lock) -
    fine for this app's single-worker dev/deploy model. Would need a
    shared store (e.g. Redis) behind multiple workers.
    """

    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, url: str) -> Job:

        job = Job(job_id=uuid4().hex, url=url)

        with self._lock:
            self._jobs[job.job_id] = job

        return job

    def get(self, job_id: str) -> Job | None:

        with self._lock:
            return self._jobs.get(job_id)

    def add_event(self, job_id: str, phase: str, data: dict) -> None:

        with self._lock:

            job = self._jobs.get(job_id)

            if job is None:
                return

            job.events.append(PhaseEvent(phase=phase, data=data))
            job.status = JobStatus.RUNNING
            job.updated_at = datetime.now()

    def complete(self, job_id: str, result: dict) -> None:

        with self._lock:

            job = self._jobs.get(job_id)

            if job is None:
                return

            job.result = result
            job.status = JobStatus.DONE
            job.updated_at = datetime.now()

    def fail(self, job_id: str, error: str) -> None:

        with self._lock:

            job = self._jobs.get(job_id)

            if job is None:
                return

            job.error = error
            job.status = JobStatus.FAILED
            job.updated_at = datetime.now()
