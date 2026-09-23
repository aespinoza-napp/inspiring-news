from logging import getLogger

from src.config.thresholds import PipelineThresholds
from src.models.core.enriched_article import EnrichedArticle
from src.models.admission.duplicate_result import DuplicateResult
from src.repositories.vector_repository import VectorRepository

logger = getLogger(__name__)


class DuplicateDetector:
    """
    Has this story already been stored - by this outlet or another?

    Owns both halves of that question: `check` searches the vector store
    for a near neighbour, `remember` adds an admitted article to it. They
    used to live apart (the search here, the save at the end of
    FactChecker.run), which is how the save once went missing and every
    check searched an empty collection.

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


    def check(
        self,
        article: EnrichedArticle,
        thresholds: PipelineThresholds | None = None,
    ) -> DuplicateResult:

        thresholds = thresholds or PipelineThresholds()


        # Excluded by URL, not only by id: every extraction mints a new id,
        # so re-analysing a URL would otherwise match its own stored copy
        # at similarity 1.0 and be rejected as a duplicate of itself.
        results = self.repository.search(
            article.embedding,
            limit=5,
            exclude_url=article.url,
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


    def remember(self, article: EnrichedArticle) -> None:
        """
        Store an admitted article so a later copy of it is caught.

        Call it only after the article's own fact-check: the same
        collection is the internal corpus EvidenceRetriever searches, and
        stored any earlier the article would turn up as evidence for its
        own claims.

        Fail-soft. The check has already been paid for; a vector store
        that cannot be written to costs the next duplicate check, not
        this run's result.
        """

        try:
            self.repository.save(article)
        except Exception:
            logger.warning("Failed to persist article %s to the vector store", article.id, exc_info=True)
