from datetime import datetime

from fastapi import APIRouter

from src.container import pipeline
from src.models.news import News
from src.workflows.news_pipeline import NewsPipeline

router = APIRouter()



@router.post("/news")
def process_news(news: News):

    return pipeline.execute(news)


@router.get("/example")
def example():

    news = News(
        title="NASA discovers new planet",
        source="cnn",
        url="https://cnn.com/example",
        published_at=datetime.now(),
        content=(
            "NASA discovered a new planet. "
            "Scientists are excited. "
            "This fake announcement spread online."
        ),
    )

    return pipeline.execute(news)