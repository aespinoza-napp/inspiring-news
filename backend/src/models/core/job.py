from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class PhaseEvent(BaseModel):

    phase: str

    data: dict[str, Any] = Field(default_factory=dict)

    at: datetime = Field(default_factory=datetime.now)


class Job(BaseModel):
    """
    Tracks one AnalysisService.analyze() run phase by phase, so a client
    can poll GET /analyze/jobs/{id} (e.g. every 1s) to see progress
    instead of blocking on a single long request.
    """

    job_id: str

    url: str

    status: JobStatus = JobStatus.QUEUED

    events: list[PhaseEvent] = Field(default_factory=list)

    result: Optional[dict] = None

    error: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.now)

    updated_at: datetime = Field(default_factory=datetime.now)
