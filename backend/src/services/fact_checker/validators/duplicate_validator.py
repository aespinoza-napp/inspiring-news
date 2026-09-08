from src.config.thresholds import PipelineThresholds
from src.models.core.enriched_article import EnrichedArticle
from src.models.fact_checker.duplicate_result import DuplicateResult
from src.repositories.vector_repository import VectorRepository
from src.config.settings import settings


class DuplicateValidator:
    """
    Thresholds come from the run's PipelineThresholds, not from class
    attributes: `X = settings.X` in a class body is evaluated once at
    import time, which froze the value for the life of the process and
    made per-run overrides impossible.
    """


    def __init__(
        self,
        repository: VectorRepository,
    ):

        self.repository = repository


    def validate(
        self,
        article: EnrichedArticle,
        thresholds: PipelineThresholds | None = None,
    ) -> DuplicateResult:

        thresholds = thresholds or PipelineThresholds()


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

        if similarity >= thresholds.duplicate_threshold:

            return DuplicateResult(
                duplicate=True,
                similarity=similarity,
                matched_article_id=best.article.id,
                reason="Duplicate article detected",
            )


        if similarity >= thresholds.relatedness_threshold:

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
