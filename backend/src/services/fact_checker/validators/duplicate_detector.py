
from src.repositories.repository import NewsRepository
from src.models.enriched_article import EnrichedArticle
from src.models.duplicate_result import DuplicateResult

class DuplicateValidator:

    def __init__(self, vector_db):

        self.vector_db = vector_db

    def is_url_duplicate(
        self,
        url: str,
        repository: NewsRepository,
    ) -> bool:

        normalized = normalize_url(url)

        return repository.exists_url(normalized)


    def validate(
        self,
        article: EnrichedArticle,
    ) -> DuplicateResult:

        neighbours = self.vector_db.search(
            article.embedding,
            limit=1,
        )

        if not neighbours:

            return DuplicateResult(
                False,
                None,
                0.0,
            )

        best = neighbours[0]

        return DuplicateResult(
            duplicate=best.similarity >= 0.95,
            duplicate_article_id=best.id,
            similarity=best.similarity,
        )