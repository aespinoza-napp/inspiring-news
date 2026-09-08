from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim
from src.models.fact_checker.evidence import Evidence, EvidenceOrigin
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

    def __init__(
        self,
        repository: VectorRepository,
        embeddings: EmbeddingService | None = None,
    ):
        self.repository = repository
        self.embeddings = embeddings or EmbeddingService()

    def retrieve(
        self,
        claim: Claim,
        limit: int = 5,
        thresholds: PipelineThresholds | None = None,
    ) -> list[Evidence]:

        minimum = (thresholds or PipelineThresholds()).relatedness_threshold

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
            if result.similarity >= minimum
        ]
