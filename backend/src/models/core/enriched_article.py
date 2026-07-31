from datetime import datetime

from pydantic import BaseModel
from typing import Optional
from src.models.nlp.topic_prediction import TopicPrediction
from src.models.core.claim import Claim
from src.models.nlp.sentiment_result import SentimentResult
from src.models.nlp.quality import Quality


class EnrichedArticle(BaseModel):

    id: str

    source_id: str

    url: str

    title: str

    body: str

    language: Optional[str] = None

    published_at: Optional[datetime] = None

    #################################################

    keywords: list[str]

    entities: dict[str, list[str]]

    topics: Optional[list[TopicPrediction]] = None

    claims: Optional[list[Claim]] = None

    sentiment: SentimentResult

    quality: Quality

    #################################################

    embedding: list[float]

    embedding_model: str

    embedding_dimension: int