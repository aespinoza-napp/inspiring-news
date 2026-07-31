from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from src.container import get_analysis_service, get_pipeline, get_text_corrector, job_store
from src.models.core.news import News
from src.services.job_runner import run_analysis_job

router = APIRouter()


class AnalyzeRequest(BaseModel):
    urls: list[str]
    forceRefresh: bool = False


class CorrectRequest(BaseModel):
    text: str


class CreateAnalysisJobRequest(BaseModel):
    url: str
    forceRefresh: bool = False


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

    return {
        "results": [
            service.analyze(url, force_refresh=request.forceRefresh)
            for url in request.urls
        ]
    }


@router.post("/analyze/jobs", status_code=202)
def create_analysis_job(request: CreateAnalysisJobRequest, background_tasks: BackgroundTasks):
    """
    Starts an analysis run in the background and returns immediately with
    a job id. Poll GET /analyze/jobs/{jobId} (e.g. every 1s) to follow its
    progress phase by phase instead of blocking on one long request.
    """

    job = job_store.create(request.url)

    background_tasks.add_task(
        run_analysis_job,
        job_store,
        get_analysis_service,  # factory, not called here - see job_runner.py
        job.job_id,
        request.url,
        request.forceRefresh,
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



@router.post("/news")
def process_news(news: News):

    return get_pipeline().execute(news)


@router.get("/example")
def example():

    news = News(
        title="NASA discovers new planet",
        source_id="cnn",
        url="https://cnn.com/example",
        published_at=datetime.now(),
        content=(
            "NASA discovered a new planet. "
            "Scientists are excited. "
            "This fake announcement spread online."
        ),
    )

    return get_pipeline().execute(news)