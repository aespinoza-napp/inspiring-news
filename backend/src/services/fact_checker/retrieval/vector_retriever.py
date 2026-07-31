from src.config.settings import settings
from src.models.claim import Claim
from src.models.evidence import Evidence, EvidenceOrigin
from src.repositories.vector_repository import VectorRepository
from src.services.embeddings.service import EmbeddingService


def _as_vector(embedding) -> list[float]:

    if hasattr(embedding, "tolist"):
        return embedding.tolist()

    return [float(value) for value in embedding]


class VectorRetriever:
    """
    Thin wrapper around VectorRepository.search(), analogous to
    DuplicateValidator: finds already-stored articles related to a
    claim and surfaces them as internal corroborating evidence.
    """

    RELATEDNESS_THRESHOLD = settings.RELATEDNESS_THRESHOLD

    def __init__(
        self,
        repository: VectorRepository,
        embeddings: EmbeddingService | None = None,
    ):
        self.repository = repository
        self.embeddings = embeddings or EmbeddingService()

    def retrieve(self, claim: Claim, limit: int = 5) -> list[Evidence]:

        embedding = self.embeddings.encode(claim.text)

        results = self.repository.search(_as_vector(embedding), limit=limit)

        return [
            Evidence(
                url=result.article.url,
                title=result.article.title,
                snippet=result.article.body[:500],
                content=result.article.body,
                source_name=result.article.source_id,
                published_at=result.article.published_at,
                origin=EvidenceOrigin.INTERNAL,
                relevance_score=result.similarity,
            )
            for result in results
            if result.similarity >= self.RELATEDNESS_THRESHOLD
        ]
