from pydantic import BaseModel


class ArticleQuality(BaseModel):

    readability: float

    objectivity: float

    constructiveness: float

    inspirational_score: float

    hopefulness: float

    societal_impact: float

    novelty: float