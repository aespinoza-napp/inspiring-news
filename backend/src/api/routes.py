from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from src.container import analysis_service, pipeline, text_corrector
from src.models.core.news import News
from src.workflows.news_pipeline import NewsPipeline

router = APIRouter()


class AnalyzeRequest(BaseModel):
    urls: list[str]


class CorrectRequest(BaseModel):
    text: str


@router.post("/analyze")
def analyze(request: AnalyzeRequest):

    return {
        "results": [
            analysis_service.analyze(url)
            for url in request.urls
        ]
    }


@router.post("/correct")
def correct(request: CorrectRequest):

    return text_corrector.correct(request.text)



@router.post("/news")
def process_news(news: News):

    return pipeline.execute(news)


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

    return pipeline.execute(news)