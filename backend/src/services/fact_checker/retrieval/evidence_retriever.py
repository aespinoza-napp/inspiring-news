from src.config.settings import settings
from src.models.core.claim import Claim
from src.models.fact_checker.evidence import Evidence, EvidenceOrigin
from src.repositories.vector_repository import VectorRepository
from src.services.embeddings.service import EmbeddingService

from .scraper import EvidenceScraper
from .search_provider import SearchProvider
from .vector_retriever import VectorRetriever


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

    def retrieve(self, claim: Claim) -> list[Evidence]:

        web_evidence = self.search_provider.search(claim)
        internal_evidence = self.vector_retriever.retrieve(claim)

        candidates = web_evidence + internal_evidence

        if not candidates:
            return []

        claim_embedding = self.embeddings.encode(claim.text)

        prescored = sorted(
            candidates,
            key=lambda evidence: self._quick_score(evidence, claim_embedding),
            reverse=True,
        )

        top_web = [
            evidence
            for evidence in prescored
            if evidence.origin == EvidenceOrigin.WEB
        ][:settings.MAX_EVIDENCE_PER_CLAIM]

        scraped = self.scraper.enrich(top_web)

        internal = [
            evidence
            for evidence in prescored
            if evidence.origin == EvidenceOrigin.INTERNAL
        ]

        return scraped + internal

    def _quick_score(self, evidence: Evidence, claim_embedding) -> float:

        text = f"{evidence.title}. {evidence.snippet}".strip()

        if not text:
            return 0.0

        return self.embeddings.similarity(
            claim_embedding,
            self.embeddings.encode(text),
        )
