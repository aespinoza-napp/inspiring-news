from dataclasses import dataclass, field

from src.config.settings import settings
from src.models.core.claim import Claim
from src.models.fact_checker.evidence import Evidence, EvidenceOrigin, RejectedEvidence
from src.models.fact_checker.pipeline_stage import PipelineStage
from src.repositories.vector_repository import VectorRepository
from src.services.embeddings.service import EmbeddingService

from .scraper import EvidenceScraper
from .search_provider import SearchProvider
from .vector_retriever import VectorRetriever


@dataclass
class RetrievalResult:

    kept: list[Evidence]

    rejected: list[RejectedEvidence] = field(default_factory=list)


class EvidenceRetriever:

    def __init__(
        self,
        repository: VectorRepository,
        search_provider: SearchProvider | None = None,
        scraper: EvidenceScraper | None = None,
        vector_retriever: VectorRetriever | None = None,
        embeddings: EmbeddingService | None = None,
    ):
        self.embeddings = embeddings or EmbeddingService()
        self.search_provider = search_provider or SearchProvider()
        self.scraper = scraper or EvidenceScraper()
        self.vector_retriever = vector_retriever or VectorRetriever(repository, self.embeddings)

    def retrieve(self, claim: Claim) -> RetrievalResult:

        web_evidence = self.search_provider.search(claim)
        internal_evidence = self.vector_retriever.retrieve(claim)

        candidates = web_evidence + internal_evidence

        if not candidates:
            return RetrievalResult(kept=[])

        claim_embedding = self.embeddings.encode(claim.text)

        scores = {
            id(evidence): self._quick_score(evidence, claim_embedding)
            for evidence in candidates
        }

        prescored = sorted(
            candidates,
            key=lambda evidence: scores[id(evidence)],
            reverse=True,
        )

        web_ranked = [
            evidence
            for evidence in prescored
            if evidence.origin == EvidenceOrigin.WEB
        ]

        top_web = web_ranked[:settings.MAX_EVIDENCE_PER_CLAIM]
        cut_web = web_ranked[settings.MAX_EVIDENCE_PER_CLAIM:]

        scraped = self.scraper.enrich(top_web)

        internal = [
            evidence
            for evidence in prescored
            if evidence.origin == EvidenceOrigin.INTERNAL
        ]

        rejected = [
            RejectedEvidence(
                url=evidence.url,
                title=evidence.title,
                origin=evidence.origin,
                stage=PipelineStage.EVIDENCE_RETRIEVAL,
                reason=(
                    f"cut by pre-rank funnel (rank {rank} of {len(web_ranked)}, "
                    f"top {settings.MAX_EVIDENCE_PER_CLAIM} kept)"
                ),
                score=scores[id(evidence)],
            )
            for rank, evidence in enumerate(cut_web, start=len(top_web) + 1)
        ]

        return RetrievalResult(kept=scraped + internal, rejected=rejected)

    def _quick_score(self, evidence: Evidence, claim_embedding) -> float:

        text = f"{evidence.title}. {evidence.snippet}".strip()

        if not text:
            return 0.0

        return self.embeddings.similarity(
            claim_embedding,
            self.embeddings.encode(text),
        )
