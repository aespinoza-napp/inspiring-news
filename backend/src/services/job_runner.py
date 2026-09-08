import logging
import time
from typing import Callable

from src.config.thresholds import PipelineThresholds
from src.services.analysis_service import AnalysisService
from src.services.job_store import JobStore

logger = logging.getLogger(__name__)

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
    thresholds: PipelineThresholds | None = None,
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

    Every phase transition is logged with how long that phase took and
    the running total, so a slow run's bottleneck (scraping vs. a
    specific claim's SearXNG search vs. the LLM call) is visible in the
    server console instead of just "it's slow" - see logging setup in
    src/main.py for why this actually shows up (INFO is not the default
    level).
    """

    start = time.monotonic()
    last = start

    def on_phase(phase: str, data: dict) -> None:

        nonlocal last

        now = time.monotonic()
        step_seconds = now - last
        total_seconds = now - start
        last = now

        logger.info(
            "[analyze %s] %s (+%.2fs, total %.2fs) url=%s",
            job_id[:8], phase, step_seconds, total_seconds, url,
        )

        if phase in _SUCCESS_PHASES:
            job_store.complete(job_id, data)
        elif phase == "failed":
            job_store.fail(job_id, data.get("error", "Unknown error"))
        else:
            job_store.add_event(job_id, phase, data)

    # Reported immediately, before anything else - building AnalysisService
    # (get_analysis_service(), below) can take ~10-15s on the first request
    # in a fresh process (loading GLiNER/embedding/sentiment models, see
    # container.py's lazy singletons) and *no* on_phase event fires during
    # that construction. Without this, the job sits at status "queued" with
    # an empty event list for up to 15s - indistinguishable from being
    # stuck - before the frontend sees anything at all.
    on_phase(
        "initializing",
        {
            "thresholdOverrides": (
                thresholds.overridden_from_defaults() if thresholds else {}
            )
        },
    )

    try:
        analysis_service = get_analysis_service()

        init_seconds = time.monotonic() - start

        on_phase("initialized", {"seconds": round(init_seconds, 2)})

        analysis_service.analyze(
            url,
            force_refresh=force_refresh,
            on_phase=on_phase,
            thresholds=thresholds,
        )
    except Exception as exc:
        total_seconds = time.monotonic() - start
        logger.warning(
            "[analyze %s] failed after %.2fs: %s", job_id[:8], total_seconds, exc
        )
        job_store.fail(job_id, str(exc))
