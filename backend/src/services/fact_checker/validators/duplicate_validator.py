from src.models.enriched_article import EnrichedArticle
from src.models.duplicate_result import DuplicateResult
from src.repositories.vector_repository import VectorRepository
from src.config.settings import settings


class DuplicateValidator:

    DUPLICATE_THRESHOLD = settings.DUPLICATE_THRESHOLD

    RELATEDNESS_THRESHOLD = settings.RELATEDNESS_THRESHOLD


    def __init__(
        self,
        repository: VectorRepository,
    ):

        self.repository = repository


    def validate(
        self,
        article: EnrichedArticle,
    ) -> DuplicateResult:


        results = self.repository.search(
            article.embedding,
            limit=5,
        )


        # Ignore the same article if it is already stored
        candidates = [
            result
            for result in results
            if result.article.id != article.id
        ]


        if not candidates:

            return DuplicateResult(
                duplicate=False,
                similarity=0.0,
                matched_article_id=None,
                reason="No similar articles found",
            )


        best = candidates[0]


        similarity = best.similarity

        if similarity >= self.DUPLICATE_THRESHOLD:

            return DuplicateResult(
                duplicate=True,
                similarity=similarity,
                matched_article_id=best.article.id,
                reason="Duplicate article detected",
            )


        if similarity >= self.RELATEDNESS_THRESHOLD:

            return DuplicateResult(
                duplicate=False,
                similarity=similarity,
                matched_article_id=best.article.id,
                reason="Related article detected",
            )


        return DuplicateResult(
            duplicate=False,
            similarity=similarity,
            matched_article_id=None,
            reason="Article is unrelated",
        )