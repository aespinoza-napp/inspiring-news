from dataclasses import dataclass, field
from typing import Callable, Optional

from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim
from src.models.fact_checker.evidence import Evidence, EvidenceOrigin, RejectedEvidence
from src.models.fact_checker.pipeline_stage import PipelineStage
from src.repositories.vector_repository import VectorRepository
from src.services.embeddings.service import EmbeddingService

from .scraper import EvidenceScraper
from .search_provider import SearchProvider
from .vector_retriever import VectorRetriever

OnPhase = Callable[[str, dict], None]


@dataclass
class RetrievalResult:

    kept: list[Evidence]

    rejected: list[RejectedEvidence] = field(default_factory=list)

    # The literal SearXNG query this retrieval used - "" when the claim
    # never reached a web search at all (e.g. a fake retriever in tests).
    query: str = ""


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

    def retrieve(
        self,
        claim: Claim,
        thresholds: PipelineThresholds | None = None,
        on_phase: Optional[OnPhase] = None,
    ) -> RetrievalResult:

        thresholds = thresholds or PipelineThresholds()

        max_evidence = thresholds.max_evidence_per_claim

        # Built once and reported before the request goes out, so what
        # actually gets searched is visible in the pipeline trace rather
        # than only inferable from the claim text - see build_query()'s
        # own docstring for why the two can diverge.
        query = self.search_provider.build_query(claim)

        if on_phase:
            on_phase("web_search_dispatched", {
                "claim": claim.text,
                "query": query,
            })

        web_evidence = self.search_provider.search(claim, thresholds)
        internal_evidence = self.vector_retriever.retrieve(
            claim,
            thresholds=thresholds,
        )

        candidates = web_evidence + internal_evidence

        if not candidates:
            return RetrievalResult(kept=[], query=query)

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

        top_web = web_ranked[:max_evidence]
        cut_web = web_ranked[max_evidence:]

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
                    f"top {max_evidence} kept)"
                ),
                score=scores[id(evidence)],
            )
            for rank, evidence in enumerate(cut_web, start=len(top_web) + 1)
        ]

        return RetrievalResult(kept=scraped + internal, rejected=rejected, query=query)

    def _quick_score(self, evidence: Evidence, claim_embedding) -> float:

        text = f"{evidence.title}. {evidence.snippet}".strip()

        if not text:
            return 0.0

        return self.embeddings.similarity(
            claim_embedding,
            self.embeddings.encode(text),
        )
