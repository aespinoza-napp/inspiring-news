from pydantic.dataclasses import dataclass

from backend.src.models.sentiment_result import SentimentResult

@dataclass
class ArticleQuality:

    sentiment: SentimentResult

    constructive_score: float

    inspirational_score: float

    motivational_score: float

    hopefulness_score: float

    objectivity_score: float

    factuality_score: float

    readability: float