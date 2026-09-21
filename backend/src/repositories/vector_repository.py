import threading
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
from src.models.core.enriched_article import EnrichedArticle
from src.models.nlp.quality import Quality
from src.models.nlp.sentiment_result import SentimentResult
from src.models.core.similarity import SimilarArticle

class VectorRepository:
    """
    The one handle on Qdrant in the process (see container.py).

    Every public method holds `_lock` for the whole of its call. The
    local-storage QdrantClient is a file-backed embedded database with
    no locking of its own, and it is now reached from several threads at
    once: claims of one article are verified concurrently (each doing an
    internal-evidence search), and up to ANALYSIS_MAX_CONCURRENCY
    articles run at the same time, one of which may be writing through
    save() while the others read. Serialising here costs nothing that
    matters - the queries are top-k over a small collection, microseconds
    beside the HTTP calls around them - and it is the only place that can
    do it, since the client is shared by construction.
    """

    COLLECTION = "news"

    def __init__(self, database: QdrantDatabase):

        self.client = database.client

        # RLock, not Lock: save() is one logical operation made of a
        # delete and an upsert, and a plain Lock would make any future
        # method that reuses another one deadlock on itself.
        self._lock = threading.RLock()

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

    @staticmethod
    def _same_url(url: str) -> Filter:

        return Filter(
            must=[FieldCondition(key="url", match=MatchValue(value=url))]
        )

    def save(
        self,
        article: EnrichedArticle,
    ):

        with self._lock:

            # One point per URL. Every extraction mints a fresh uuid4 id,
            # so without this a re-analysis of the same URL stored a
            # second copy beside the first - and the copies then crowd
            # the top-k of every duplicate and internal-evidence search
            # with the article itself.
            self.client.delete(
                collection_name=self.COLLECTION,
                points_selector=self._same_url(article.url),
                wait=True,
            )

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

        with self._lock:
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
        exclude_url: str | None = None,
    ) -> list[SimilarArticle]:
        """
        `exclude_url` drops the article at that URL *inside* the query, so
        the limit is spent on other articles. Filtering the results
        afterwards would leave fewer than `limit` real neighbours.
        """

        with self._lock:
            results = self.client.query_points(
                collection_name=self.COLLECTION,
                query=vector,
                limit=limit,
                query_filter=(
                    Filter(must_not=[
                        FieldCondition(key="url", match=MatchValue(value=exclude_url))
                    ])
                    if exclude_url
                    else None
                ),
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

        with self._lock:
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

        with self._lock:
            return self.client.count(
                collection_name=self.COLLECTION,
                exact=True,
            ).count

    def clear(self):

        with self._lock:
            self.client.delete(
                collection_name=self.COLLECTION,
                points_selector=Filter(),
                wait=True,
            )
