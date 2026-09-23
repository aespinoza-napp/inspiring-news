import secrets
from logging import getLogger

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from src.container import (
    get_analysis_service,
    get_claim_service,
    get_datalake_repository,
    get_enrichment_service,
    get_job_queue,
    get_text_corrector,
    job_store,
)
from src.config.settings import settings
from src.config.thresholds import PipelineThresholds, ThresholdOverrides
from src.models.core.job import JobStatus
from src.models.storage.lineage import DataLayer
from src.services.enrichment_service import NothingToEnrich
from src.services.job_runner import run_analysis_job
from src.services.scraper.article_stats import article_stats
from src.services.scraper.request_stats import request_stats

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
    # Either may be omitted, not both. A URL is fetched with the
    # analyzer's own extractor; pasted text, when also given, wins over
    # the fetched body.
    text: str | None = None
    title: str | None = None
    url: str | None = None
    # Omit to let the pipeline detect it. "en" and "es" are the two
    # supported lexicons; anything else is scored with the English one.
    language: str | None = Field(default=None, max_length=8)
    thresholds: ThresholdOverrides | None = None

    @model_validator(mode="after")
    def _text_or_url(self):
        if not (self.text or "").strip() and not (self.url or "").strip():
            raise ValueError("Provide the article text, a URL, or both.")
        return self


class CreateAnalysisJobRequest(BaseModel):
    url: str
    forceRefresh: bool = False
    thresholds: ThresholdOverrides | None = None


class CreateAnalysisJobsBatchRequest(BaseModel):
    urls: list[str]
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


def _start_job(url: str, force_refresh: bool, thresholds: PipelineThresholds) -> tuple[str, bool]:
    """
    Shared by the single and batch job routes: dedupes onto any job
    already in flight for this exact URL, otherwise creates one and
    submits it to the bounded job queue (see src/services/job_queue.py).
    Returns (jobId, reused).
    """

    job, reused = job_store.get_or_create(url)

    if not reused:
        get_job_queue().submit(
            run_analysis_job,
            job_store,
            get_analysis_service,  # factory, not called here - see job_runner.py
            job.job_id,
            url,
            force_refresh,
            thresholds,
        )

    return job.job_id, reused


@router.post("/analyze/jobs", status_code=202)
def create_analysis_job(request: CreateAnalysisJobRequest):
    """
    Starts an analysis run on the bounded job queue and returns
    immediately with a job id. Poll GET /analyze/jobs/{jobId} (e.g. every
    1s) to follow its progress phase by phase instead of blocking on one
    long request. A second call for a URL already in flight reuses that
    job instead of starting a duplicate run.
    """

    # Resolved here, on the request thread, so an out-of-range override
    # is a 422 on the POST rather than a job that starts and then fails.
    thresholds = PipelineThresholds.resolve(request.thresholds)

    job_id, _ = _start_job(request.url, request.forceRefresh, thresholds)

    return {"jobId": job_id}


@router.post("/analyze/jobs/batch", status_code=202)
def create_analysis_jobs_batch(request: CreateAnalysisJobsBatchRequest):
    """
    Bulk form of POST /analyze/jobs: submits every URL onto the same
    bounded job queue and returns a job id per URL, in input order, so a
    client can poll them (individually, or via GET /analyze/jobs/batch)
    as a single parallel workflow instead of one request per URL.

    Duplicate URLs in the same batch - or a URL already in flight from an
    earlier call - reuse the existing job's id rather than running the
    pipeline twice for it; the response still carries one entry per input
    URL so the caller can see which ones were deduped.
    """

    thresholds = PipelineThresholds.resolve(request.thresholds)

    jobs = [
        {"url": url, "jobId": _start_job(url, request.forceRefresh, thresholds)[0]}
        for url in request.urls
    ]

    return {"jobs": jobs}


def _job_view(job, with_events: bool = True, with_result: bool = True) -> dict:
    return {
        "jobId": job.job_id,
        "url": job.url,
        "kind": job.kind,
        "status": job.status,
        "events": [
            {"phase": event.phase, "data": event.data, "at": event.at}
            for event in job.events
        ] if with_events else [],
        "eventCount": len(job.events),
        "result": job.result if with_result else None,
        "error": job.error,
        "createdAt": job.created_at,
        "updatedAt": job.updated_at,
    }


@router.get("/analyze/jobs", dependencies=[Depends(require_storage_key)])
def list_analysis_jobs(limit: int = Query(default=20, ge=1, le=100)):
    """
    What is running now and what ran recently, for a second screen that
    wants to watch verification happen without having started it.

    Active jobs come first and carry every event, so the viewer can draw
    the searches, sources and ratings as they arrive. Finished jobs are
    summarised without their events or their result (a long run is
    hundreds of KB, and this is polled every second) - fetch one by id for
    the full record. Only jobs this process holds are listed; earlier runs
    stay readable by id from the journal.

    Behind the same optional key as /storage/*: a job id used to be a
    capability nobody could guess, and this lists every one of them along
    with the URLs and claims people submitted.
    """

    return {
        "jobs": [
            _job_view(
                job,
                with_events=job.status in (JobStatus.QUEUED, JobStatus.RUNNING),
                with_result=False,
            )
            for job in job_store.list(limit)
        ]
    }


@router.get("/analyze/jobs/batch")
def get_analysis_jobs_batch(ids: str):
    """
    Polls several jobs in one round trip: ids is a comma-separated list
    of job ids, as returned by POST /analyze/jobs/batch. Unknown ids
    come back as {"status": "not_found"} entries rather than failing the
    whole request - a batch is expected to still have jobs in flight
    while others have already been polled to completion elsewhere.
    """

    job_ids = [job_id for job_id in ids.split(",") if job_id]

    results = []

    for job_id in job_ids:
        job = job_store.get(job_id)
        if job is None:
            results.append({"jobId": job_id, "status": "not_found"})
        else:
            results.append(_job_view(job))

    return {"jobs": results}


@router.get("/analyze/jobs/{job_id}")
def get_analysis_job(job_id: str):

    job = job_store.get(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return _job_view(job)


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

    # Registered as a job so a second screen can watch the verification
    # and the journal keeps it, even though this request still answers
    # synchronously.
    job = job_store.create(request.claim, kind="claim")

    def on_phase(phase: str, data: dict) -> None:

        if phase == "done":
            job_store.complete(job.job_id, data)
        else:
            job_store.add_event(job.job_id, phase, data)

    try:
        return service.verify(request.claim, on_phase=on_phase, thresholds=thresholds)
    except Exception as exc:
        job_store.fail(job.job_id, str(exc))
        raise


@router.post("/enrich")
def enrich(request: EnrichRequest):
    """
    Run only the NLP enrichment stage over supplied text: keywords,
    entities, topics, claims, sentiment, quality and the embedding.

    Reuses NewsEnrichmentPipeline exactly as the article pipeline does,
    so the output matches what a full run would derive from the same
    text. With a `url`, the page is first fetched with the analyzer's
    extractor and `extraction` reports the title, author, date and body
    it produced. Nothing is stored - this is for inspecting and tuning
    ("what would the pipeline make of this, at these thresholds?"), not
    for ingesting articles.
    """

    thresholds = PipelineThresholds.resolve(request.thresholds)

    try:
        service = get_enrichment_service()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Enrichment unavailable: {exc}",
        )

    try:
        return service.enrich(
            request.text,
            title=request.title,
            url=request.url,
            language=request.language,
            thresholds=thresholds,
        )
    except NothingToEnrich as exc:
        raise HTTPException(status_code=422, detail=str(exc))

# ---------------------------------------------------------------------
# Scraper request stats
# ---------------------------------------------------------------------


@router.get("/scraper/stats", dependencies=[Depends(require_storage_key)])
def scraper_stats():
    """
    Every page fetch this process has made - article, evidence and
    enrichment alike - counted per domain, with what each came to (ok,
    too short, HTTP error, timeout, blocked...). Behind the storage key
    because it names every URL the server has been asked to read.
    """

    return request_stats.snapshot()


@router.get("/scraper/articles", dependencies=[Depends(require_storage_key)])
def scraped_articles():
    """
    What the scraper has to show for its requests: articles stored in the
    lake's raw layer, per domain - how many, how many distinct, how many
    arrived with a title, author and date, and how many went on to be
    processed, stored and published. Read from the lake on each call.
    """

    return article_stats(get_datalake_repository())


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
