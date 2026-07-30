from pydantic import BaseModel

from src.models.enriched_article import EnrichedArticle


class SimilarArticle(BaseModel):

    article: EnrichedArticle

    similarity: float