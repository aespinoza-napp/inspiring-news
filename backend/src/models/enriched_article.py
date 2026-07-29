from pydantic import BaseModel
from typing import Optional
from src.models.topic_prediction import TopicPrediction
from src.models.claim import Claim
from src.models.sentiment_result import SentimentResult
from src.models.quality import Quality


class EnrichedArticle(BaseModel):

    id: str

    source_id: str

    url: str

    title: str

    body: str

    language: Optional[str] = None

    #################################################

    keywords: list[str]

    entities: dict[str, list[str]]

    topics: list[TopicPrediction]

    claims: list[Claim]

    sentiment: SentimentResult

    quality: Quality

    #################################################

    embedding: list[float]

    embedding_model: str

    embedding_dimension: int