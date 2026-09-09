import secrets
from logging import getLogger

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from src.container import (
    get_analysis_service,
    get_claim_service,
    get_datalake_repository,
    get_enrichment_service,
    get_text_corrector,
    job_store,
)
from src.config.settings import settings
from src.config.thresholds import PipelineThresholds, ThresholdOverrides
from src.models.storage.lineage import DataLayer
from src.services.job_runner import run_analysis_job

logger = getLogger(__name__)

router = APIRouter()


def require_storage_key(x_api_key: str | None = Header(default=None)) -> None:
    """
    Guards the /storage/* endpoints, which return whole article bodies
    and the full lineage of every run.

    Open when STORAGE_API_KEY is unset - the local-dev default, and
    src/main.py logs a warning at startup so that is never a silent
    choice. Compared with secrets.compare_digest so a wrong key cannot be
    recovered by timing the response.
    """

    expected = settings.STORAGE_API_KEY

    if expected is None:
        return

    if not x_api_key or not secrets.compare_digest(
        x_api_key, expected.get_secret_value()
    ):
        raise HTTPException(
            status_code=401,
            detail="A valid X-API-Key header is required for storage endpoints.",
        )


class AnalyzeRequest(BaseModel):
    urls: list[str]
    forceRefresh: bool = False

    # Per-run threshold overrides. Send only the knobs you want to
    # change; anything omitted falls back to the environment default
    # (settings.*). Out-of-range values are rejected with a 422 by
    # ThresholdOverrides rather than reaching the pipeline.
    thresholds: ThresholdOverrides | None = None


class CorrectRequest(BaseModel):
    text: str


class VerifyClaimRequest(BaseModel):
    claim: str = Field(min_length=1, max_length=2000)
    thresholds: ThresholdOverrides | None = None


class EnrichRequest(BaseModel):
    text: str = Field(min_length=1)
    title: str | None = None
    url: str | None = None
    # Omit to let the pipeline detect it. "en" and "es" are the two
    # supported lexicons; anything else is scored with the English one.
    language: str | None = Field(default=None, max_length=8)
    thresholds: ThresholdOverrides | None = None


class CreateAnalysisJobRequest(BaseModel):
    url: str
    forceRefresh: bool = False
    thresholds: ThresholdOverrides | None = None


@router.post("/analyze")
def analyze(request: AnalyzeRequest):

    try:
        service = get_analysis_service()
    except Exception as exc:
        return {
            "results": [
                {"url": url, "error": f"Analysis service unavailable: {exc}"}
                for url in request.urls
            ]
        }

    thresholds = PipelineThresholds.resolve(request.thresholds)

    results = []

    for url in request.urls:

        # Per URL, not per batch. AnalysisService only catches extraction
        # failures internally; anything raised later (enrichment, the
        # fact-checker, storage) propagated out of the whole request, so
        # one unusual URL discarded the completed results for every other
        # URL in the same call.
        try:
            results.append(
                service.analyze(
                    url,
                    force_refresh=request.forceRefresh,
                    thresholds=thresholds,
                )
            )
        except Exception as exc:
            logger.warning("Analysis failed for %s", url, exc_info=True)
            results.append({"url": url, "error": f"Analysis failed: {exc}"})

    return {"results": results}


@router.post("/analyze/jobs", status_code=202)
def create_analysis_job(request: CreateAnalysisJobRequest, background_tasks: BackgroundTasks):
    """
    Starts an analysis run in the background and returns immediately with
    a job id. Poll GET /analyze/jobs/{jobId} (e.g. every 1s) to follow its
    progress phase by phase instead of blocking on one long request.
    """

    # Resolved here, on the request thread, so an out-of-range override
    # is a 422 on the POST rather than a job that starts and then fails.
    thresholds = PipelineThresholds.resolve(request.thresholds)

    job = job_store.create(request.url)

    background_tasks.add_task(
        run_analysis_job,
        job_store,
        get_analysis_service,  # factory, not called here - see job_runner.py
        job.job_id,
        request.url,
        request.forceRefresh,
        thresholds,
    )

    return {"jobId": job.job_id}


@router.get("/analyze/jobs/{job_id}")
def get_analysis_job(job_id: str):

    job = job_store.get(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "jobId": job.job_id,
        "url": job.url,
        "status": job.status,
        "events": [
            {"phase": event.phase, "data": event.data, "at": event.at}
            for event in job.events
        ],
        "result": job.result,
        "error": job.error,
    }


@router.post("/correct")
def correct(request: CorrectRequest):

    return get_text_corrector().correct(request.text)


@router.post("/verify-claim")
def verify_claim(request: VerifyClaimRequest):
    """
    Verify one claim on its own - no article, no scraping.

    Runs the article pipeline's verification stage unchanged (evidence
    retrieval -> ranking -> LLM -> confidence recalibration), so a claim
    checked here gets the same verdict it would get inside a full run.
    The article-level gates (topic relevance, positive impact, duplicate
    detection, claim selection) do not apply and are skipped: they judge
    an article, and a bare claim is not one.

    Synchronous, like POST /analyze: it still costs a live search plus
    one LLM call, but only one, so it does not need the job machinery.
    """

    thresholds = PipelineThresholds.resolve(request.thresholds)

    try:
        service = get_claim_service()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Claim verification unavailable: {exc}",
        )

    return service.verify(request.claim, thresholds=thresholds)


@router.post("/enrich")
def enrich(request: EnrichRequest):
    """
    Run only the NLP enrichment stage over supplied text: keywords,
    entities, topics, claims, sentiment, quality and the embedding.

    Reuses NewsEnrichmentPipeline exactly as the article pipeline does,
    so the output matches what a full run would derive from the same
    text. Nothing is fetched and nothing is stored - this is for
    inspecting and tuning ("what would the pipeline make of this, at
    these thresholds?"), not for ingesting articles.
    """

    thresholds = PipelineThresholds.resolve(request.thresholds)

    try:
        service = get_enrichment_service()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Enrichment unavailable: {exc}",
        )

    return service.enrich(
        request.text,
        title=request.title,
        url=request.url,
        language=request.language,
        thresholds=thresholds,
    )

# ---------------------------------------------------------------------
# Storage layers
#
# Read-only views over the three-layer lake the analysis pipeline writes
# to (raw -> processed -> exploitation). `layer` is the DataLayer enum,
# so FastAPI rejects an unknown layer with a 422 before any I/O happens.
# ---------------------------------------------------------------------


@router.get("/storage/{layer}", dependencies=[Depends(require_storage_key)])
def list_records(layer: DataLayer, limit: int = 50):

    return {
        "layer": layer,
        "records": get_datalake_repository().list(layer, limit=limit),
    }


@router.get(
    "/storage/{layer}/records/{record_id}",
    dependencies=[Depends(require_storage_key)],
)
def get_record(layer: DataLayer, record_id: str):

    record = get_datalake_repository().get(layer, record_id)

    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")

    return record


@router.get("/storage/trace/{article_id}", dependencies=[Depends(require_storage_key)])
def trace_article(article_id: str):
    """
    The full lineage chain for one article: its record in each layer,
    plus the manifest entries that recorded those writes. Answers "which
    fetch, which run and which model versions produced this served
    document".
    """

    return get_datalake_repository().trace(article_id)
