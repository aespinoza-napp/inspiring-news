from dataclasses import dataclass, field

from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim
from src.models.fact_checker.evidence import Evidence, EvidenceOrigin, RejectedEvidence
from src.models.fact_checker.pipeline_stage import PipelineStage
from src.repositories.vector_repository import VectorRepository
from src.services.embeddings.service import EmbeddingService
from src.services.fact_checker.claim_selector import ArticleContext

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

    def retrieve(
        self,
        claim: Claim,
        thresholds: PipelineThresholds | None = None,
        context: ArticleContext | None = None,
        language: str | None = None,
    ) -> RetrievalResult:

        thresholds = thresholds or PipelineThresholds()

        max_evidence = thresholds.max_evidence_per_claim

        web_evidence = self.search_provider.search(
            claim,
            thresholds,
            context=context,
            language=language,
        )
        internal_evidence = self.vector_retriever.retrieve(
            claim,
            thresholds=thresholds,
        )

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

        web_ranked, same_domain = self._one_per_domain(web_ranked)

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
        ] + same_domain

        return RetrievalResult(kept=scraped + internal, rejected=rejected)

    def _one_per_domain(
        self,
        evidence: list[Evidence],
    ) -> tuple[list[Evidence], list[RejectedEvidence]]:
        """
        Keeps the best-scoring hit per domain.

        Corroboration is the whole point of retrieving several sources,
        and a wire story republished by five outlets is one source wearing
        five hats. Without this the evidence set fills up with copies of
        the same text, the LLM sees five agreeing documents, and the
        confidence scorer counts five independent confirmations of
        something exactly one newsroom reported.

        `evidence` is already sorted best-first, so the first hit seen for
        a domain is the one worth keeping.
        """

        kept: list[Evidence] = []
        seen: set[str] = set()
        dropped: list[RejectedEvidence] = []

        for item in evidence:

            domain = item.domain or item.url

            if domain in seen:
                dropped.append(RejectedEvidence(
                    url=item.url,
                    title=item.title,
                    origin=item.origin,
                    stage=PipelineStage.EVIDENCE_RETRIEVAL,
                    reason=f"same domain as a higher-ranked source ({domain})",
                    score=item.relevance_score,
                ))
                continue

            seen.add(domain)
            kept.append(item)

        return kept, dropped

    def _quick_score(self, evidence: Evidence, claim_embedding) -> float:

        text = f"{evidence.title}. {evidence.snippet}".strip()

        if not text:
            return 0.0

        return self.embeddings.similarity(
            claim_embedding,
            self.embeddings.encode(text),
        )
