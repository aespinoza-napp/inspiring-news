from datetime import datetime

from qdrant_client.models import (
    Distance,
    Filter,
    FieldCondition,
    MatchValue,
    PointIdsList,
    PointStruct,
    VectorParams,
)

from src.config.settings import settings
from src.database.qdrant import QdrantDatabase
from src.models.enriched_article import EnrichedArticle
from src.models.quality import Quality
from src.models.sentiment_result import SentimentResult
from src.models.similarity import SimilarArticle

class VectorRepository:

    COLLECTION = "news"

    def __init__(self, database: QdrantDatabase):

        self.client = database.client

        self._create_collection()

    def _create_collection(self):

        collections = self.client.get_collections().collections

        if self.COLLECTION not in [c.name for c in collections]:

            self.client.create_collection(
                collection_name=self.COLLECTION,
                vectors_config=VectorParams(
                    size=settings.EMBEDDING_DIMENSION,
                    distance=Distance.COSINE,
                ),
            )

    def _to_point(
        self,
        article: EnrichedArticle,
    ) -> PointStruct:

        return PointStruct(
            id=article.id,
            vector=article.embedding,
            payload=article.model_dump(mode="json"),
        )

    def _to_article(
        self,
        point,
    ) -> EnrichedArticle:

        payload = dict(point.payload)

        payload["embedding"] = point.vector

        return EnrichedArticle.model_validate(payload)

    def save(
        self,
        article: EnrichedArticle,
    ):

        self.client.upsert(
            collection_name=self.COLLECTION,
            wait=True,
            points=[
                self._to_point(article)
            ],
        )

    def get(
        self,
        article_id: str,
    ) -> EnrichedArticle | None:

        result = self.client.retrieve(
            collection_name=self.COLLECTION,
            ids=[article_id],
            with_payload=True,
            with_vectors=True,
        )

        if not result:
            return None

        return self._to_article(result[0])

    def search(
        self,
        vector: list[float],
        limit: int = 5,
    ) -> list[SimilarArticle]:


        results = self.client.query_points(
            collection_name=self.COLLECTION,
            query=vector,
            limit=limit,
            with_payload=True,
            with_vectors=True,
        )


        return [
            SimilarArticle(
                article=self._to_article(point),
                similarity=point.score,
            )
            for point in results.points
        ]

    def delete(
        self,
        article_id: str,
    ):

        self.client.delete(
            collection_name=self.COLLECTION,
            points_selector=PointIdsList(
                points=[article_id],
            ),
            wait=True,
        )

    def exists(
        self,
        article_id: str,
    ) -> bool:

        return self.get(article_id) is not None

    def count(self) -> int:

        return self.client.count(
            collection_name=self.COLLECTION,
            exact=True,
        ).count

    def clear(self):

        self.client.delete(
            collection_name=self.COLLECTION,
            points_selector=Filter(),
            wait=True,
        )