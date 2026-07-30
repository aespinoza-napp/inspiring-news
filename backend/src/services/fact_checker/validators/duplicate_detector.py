from src.models.enriched_article import EnrichedArticle
from src.models.duplicate_result import DuplicateResult
from src.repositories.vector_repository import VectorRepository
from config.settings import settings

class DuplicateValidator:


    DUPLICATE_THRESHOLD = settings.DUPLICATE_THRESHOLD


    def __init__(
        self,
        repository: VectorRepository,
    ):

        self.repository = repository


    def validate(
        self,
        article: EnrichedArticle,
    ) -> DuplicateResult:


        similar_articles = self.repository.search(
            article.embedding,
            limit=5,
        )


        # remove itself if it already exists
        candidates = [
            item
            for item in similar_articles
            if item.id != article.id
        ]


        if not candidates:

            return DuplicateResult(
                duplicate=False,
                similarity=0.0,
                reason="No similar articles found",
            )


        # because Qdrant returns nearest neighbours
        most_similar = candidates[0]


        similarity = self.repository.last_similarity


        return DuplicateResult(
            duplicate=similarity >= self.DUPLICATE_THRESHOLD,
            similarity=similarity,
            matched_article_id=most_similar.id,
            reason=(
                "Similar article found"
                if similarity >= self.DUPLICATE_THRESHOLD
                else "Article is different"
            ),
        )