from pydantic import BaseModel

from src.models.core.enriched_article import EnrichedArticle


class SimilarArticle(BaseModel):

    article: EnrichedArticle

    similarity: float