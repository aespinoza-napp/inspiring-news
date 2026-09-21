from dataclasses import dataclass, field
from typing import Callable, Optional

from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim
from src.models.fact_checker.evidence import Evidence, EvidenceOrigin, RejectedEvidence
from src.models.fact_checker.pipeline_stage import PipelineStage
from src.repositories.vector_repository import VectorRepository
from src.services.embeddings.service import EmbeddingService
from src.services.fact_checker.claim_selector import ArticleContext
from src.services.fact_checker.progress import source_summary

from .scraper import EvidenceScraper
from .search_provider import SearchProvider
from .vector_retriever import VectorRetriever

OnPhase = Callable[[str, dict], None]


def _noop(phase: str, data: dict) -> None:
    pass


@dataclass
class RetrievalResult:

    kept: list[Evidence]

    rejected: list[RejectedEvidence] = field(default_factory=list)

    # What was actually sent to the search engine for this claim.
    queries: list[str] = field(default_factory=list)


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
        on_phase: Optional[OnPhase] = None,
    ) -> RetrievalResult:

        thresholds = thresholds or PipelineThresholds()

        report = on_phase or _noop

        max_evidence = thresholds.max_evidence_per_claim

        # Announced before the search runs, not after: the search is the
        # slow part, and this is what lets a second screen show what is
        # being looked up while the answer is still pending.
        queries = self.search_provider.queries_for(claim, context, language)

        report("searching_web", {
            "claim": claim.text,
            "queries": queries,
            "candidates": thresholds.evidence_fetch_candidates,
        })

        web_evidence = self.search_provider.search(
            claim,
            thresholds,
            context=context,
            language=language,
        )
        internal_evidence = self.vector_retriever.retrieve(
            claim,
            thresholds=thresholds,
            exclude_url=context.url if context and context.url else None,
        )

        candidates = web_evidence + internal_evidence

        if not candidates:
            report("web_results", {
                "claim": claim.text,
                "queries": queries,
                "webCount": 0,
                "internalCount": 0,
                "results": [],
            })
            return RetrievalResult(kept=[], queries=queries)

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

        report("web_results", {
            "claim": claim.text,
            "queries": queries,
            "webCount": len(web_evidence),
            "internalCount": len(internal_evidence),
            # Every candidate the search returned, before any is cut, with
            # the cheap similarity that decides which get scraped.
            "results": [
                {**source_summary(evidence), "quickScore": scores[id(evidence)]}
                for evidence in prescored
            ],
        })

        web_ranked = [
            evidence
            for evidence in prescored
            if evidence.origin == EvidenceOrigin.WEB
        ]

        web_ranked, same_domain = self._one_per_domain(web_ranked)

        top_web = web_ranked[:max_evidence]
        cut_web = web_ranked[max_evidence:]

        report("scraping_sources", {
            "claim": claim.text,
            "sources": [
                {"url": evidence.url, "domain": evidence.domain}
                for evidence in top_web
            ],
        })

        scraped = self.scraper.enrich(top_web)

        report("sources_scraped", {
            "claim": claim.text,
            "sources": [
                {"url": evidence.url, "scraped": bool(evidence.content)}
                for evidence in scraped
            ],
        })

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

        return RetrievalResult(
            kept=scraped + internal,
            rejected=rejected,
            queries=queries,
        )

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
