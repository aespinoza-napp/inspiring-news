import json
import re
from datetime import datetime
from logging import getLogger
from pathlib import Path

from src.models.core.job import Job, JobStatus, PhaseEvent

logger = getLogger(__name__)

# Job ids are uuid4().hex. GET /analyze/jobs/{id} takes the id from the
# client and falls back to reading it from disk, so anything that is not
# exactly that shape must never reach a path join ("../../x").
_JOB_ID = re.compile(r"[0-9a-f]{32}")


class JobJournal:
    """
    Append-only record of every job: one JSONL file per job, one line per
    thing that happened to it.

    JobStore keeps jobs in memory, so a crash, a restart or a failed run
    used to take everything with it - including the searches made, the
    sources found and how each was rated, which is exactly what someone
    debugging a bad verdict needs. Each line is written as it happens, so
    a run that dies halfway still leaves everything up to that point.

    Nothing is created until the first write, so constructing one has no
    side effects. Like the lake it has no default location: the app
    attaches one at startup (see src/main.py) and tests simply do not.
    """

    def __init__(self, directory: Path):

        self.directory = Path(directory)

    def append(self, job_id: str, type_: str, **payload) -> None:
        """Fail-soft: a full disk must not stop the analysis it records."""

        try:
            path = self._path(job_id)

            if path is None:
                return

            self.directory.mkdir(parents=True, exist_ok=True)

            line = {"at": datetime.now().isoformat(), "type": type_, **payload}

            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(line, default=str) + "\n")

        except Exception:
            logger.warning("Could not journal %s for job %s", type_, job_id, exc_info=True)

    def load(self, job_id: str) -> Job | None:
        """
        Rebuilds a job from its file. A job with no terminal line was cut
        off - the process died mid-run - and is reported as failed rather
        than left looking as if it might still be running.
        """

        path = self._path(job_id)

        if path is None or not path.exists():
            return None

        job: Job | None = None

        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return None

        for raw in lines:

            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                # A torn final line from a crash mid-write.
                continue

            type_ = entry.get("type")
            at = self._parse(entry.get("at"))

            if type_ == "created":
                job = Job(
                    job_id=job_id,
                    url=entry.get("url", ""),
                    kind=entry.get("kind", "article"),
                    created_at=at,
                    updated_at=at,
                )

            elif job is None:
                continue

            elif type_ == "event":
                job.events.append(PhaseEvent(
                    phase=entry.get("phase", ""),
                    data=entry.get("data") or {},
                    at=at,
                ))
                job.status = JobStatus.RUNNING
                job.updated_at = at

            elif type_ == "result":
                job.result = entry.get("result")
                job.status = JobStatus.DONE
                job.updated_at = at

            elif type_ == "error":
                job.error = entry.get("error")
                job.status = JobStatus.FAILED
                job.updated_at = at

        if job is not None and job.status in (JobStatus.QUEUED, JobStatus.RUNNING):
            job.status = JobStatus.FAILED
            job.error = "Interrupted: the server stopped before this run finished."

        return job

    def _path(self, job_id: str) -> Path | None:

        if not _JOB_ID.fullmatch(job_id or ""):
            return None

        return self.directory / f"{job_id}.jsonl"

    @staticmethod
    def _parse(value) -> datetime:

        try:
            return datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return datetime.now()
