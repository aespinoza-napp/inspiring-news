from src.services.analysis_service import AnalysisService
from src.services.job_store import JobStore

# Phases AnalysisService.analyze() treats as a final outcome - see
# analysis_service.py: "done" (pipeline ran to completion), "cache_hit"
# (short-circuited, but still a complete result), "failed" (error).
_SUCCESS_PHASES = ("done", "cache_hit")


def run_analysis_job(
    job_store: JobStore,
    analysis_service: AnalysisService,
    job_id: str,
    url: str,
    force_refresh: bool = False,
) -> None:
    """
    Runs AnalysisService.analyze() for one URL, writing each phase into
    job_store as it happens. Meant to run in a background task/thread -
    GET /analyze/jobs/{id} polls job_store for progress while this runs.
    """

    def on_phase(phase: str, data: dict) -> None:

        if phase in _SUCCESS_PHASES:
            job_store.complete(job_id, data)
        elif phase == "failed":
            job_store.fail(job_id, data.get("error", "Unknown error"))
        else:
            job_store.add_event(job_id, phase, data)

    try:
        analysis_service.analyze(url, force_refresh=force_refresh, on_phase=on_phase)
    except Exception as exc:
        job_store.fail(job_id, str(exc))
