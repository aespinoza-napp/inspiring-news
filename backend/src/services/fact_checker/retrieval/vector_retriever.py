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
    DuplicateDetector (admission): finds already-stored articles related to a
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
        exclude_url: str | None = None,
        embedding=None,
    ) -> list[Evidence]:
        """
        `exclude_url` is the article the claim came from: its own earlier
        copy must not come back as "independent" corroboration of itself.

        `embedding` is the claim's vector when the caller already has it.
        EvidenceRetriever does: it embeds the claim inside its article
        (`contextualised_claim`) a moment before, to score the web
        candidates. Encoding the bare text again here cost a second call
        to inference/ per claim - behind its single permit, so queued
        behind other claims' batches - and searched the corpus for the
        claim out of its article's sense, the thing the contextualised
        vector exists to avoid. With no article the two texts are equal.
        """

        minimum = (thresholds or PipelineThresholds()).relatedness_threshold

        if embedding is None:
            embedding = self.embeddings.encode(claim.text)

        results = self.repository.search(
            _as_vector(embedding),
            limit=limit,
            exclude_url=exclude_url,
        )

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
