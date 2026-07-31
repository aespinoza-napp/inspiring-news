from typing import Callable

from src.services.analysis_service import AnalysisService
from src.services.job_store import JobStore

# Phases AnalysisService.analyze() treats as a final outcome - see
# analysis_service.py: "done" (pipeline ran to completion), "cache_hit"
# (short-circuited, but still a complete result), "failed" (error).
_SUCCESS_PHASES = ("done", "cache_hit")


def run_analysis_job(
    job_store: JobStore,
    get_analysis_service: Callable[[], AnalysisService],
    job_id: str,
    url: str,
    force_refresh: bool = False,
) -> None:
    """
    Runs AnalysisService.analyze() for one URL, writing each phase into
    job_store as it happens. Meant to run in a background task/thread -
    GET /analyze/jobs/{id} polls job_store for progress while this runs.

    Takes a factory (get_analysis_service), not an already-built
    AnalysisService: building one connects to Qdrant (see
    src/container.py's lazy get_analysis_service/get_vector_repository),
    which can fail (e.g. a transient local-storage lock conflict). That
    construction must happen *inside* this function's try/except, in the
    background thread - not eagerly in the route handler, where a
    failure would 500 the request itself instead of landing here as a
    clean job_store.fail().
    """

    def on_phase(phase: str, data: dict) -> None:

        if phase in _SUCCESS_PHASES:
            job_store.complete(job_id, data)
        elif phase == "failed":
            job_store.fail(job_id, data.get("error", "Unknown error"))
        else:
            job_store.add_event(job_id, phase, data)

    try:
        analysis_service = get_analysis_service()
        analysis_service.analyze(url, force_refresh=force_refresh, on_phase=on_phase)
    except Exception as exc:
        job_store.fail(job_id, str(exc))
