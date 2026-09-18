import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional
from urllib.parse import urlparse

from src.config.settings import settings
from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim
from src.models.fact_checker.evidence import Evidence, RejectedEvidence
from src.models.fact_checker.pipeline_stage import PipelineStage
from src.repositories.source_repository import SourceRepository
from src.services.embeddings.service import EmbeddingService

OnPhase = Callable[[str, dict], None]


@dataclass
class RankingResult:

    kept: list[Evidence]

    rejected: list[RejectedEvidence] = field(default_factory=list)


class EvidenceRanker:

    SEMANTIC_WEIGHT = settings.RANKING_SEMANTIC_WEIGHT
    RECENCY_WEIGHT = settings.RANKING_RECENCY_WEIGHT
    RELIABILITY_WEIGHT = settings.RANKING_RELIABILITY_WEIGHT

    DEFAULT_RELIABILITY = settings.RANKING_DEFAULT_RELIABILITY

    RECENCY_HALF_LIFE_DAYS = settings.EVIDENCE_RECENCY_HALF_LIFE_DAYS

    def __init__(
        self,
        embeddings: EmbeddingService | None = None,
        source_repository: SourceRepository | None = None,
    ):
        self.embeddings = embeddings or EmbeddingService()
        self._reliability_by_domain = self._load_domain_reliability(
            source_repository or SourceRepository()
        )

    def rank(
        self,
        claim: Claim,
        evidence: list[Evidence],
        thresholds: PipelineThresholds | None = None,
        on_phase: Optional[OnPhase] = None,
    ) -> RankingResult:

        max_evidence = (thresholds or PipelineThresholds()).max_evidence_per_claim

        if not evidence:
            return RankingResult(kept=[])

        claim_embedding = self.embeddings.encode(claim.text)

        scored = []

        for item in evidence:

            score, breakdown = self._score(item, claim_embedding)

            scored.append(item.model_copy(update={
                "relevance_score": score,
                "relevance_note": breakdown,
            }))

        scored.sort(key=lambda item: item.relevance_score, reverse=True)

        kept = [
            item.model_copy(update={
                "relevance_note": f"{item.relevance_note} — ranked #{rank} of {len(scored)}",
            })
            for rank, item in enumerate(scored[:max_evidence], start=1)
        ]

        cut = scored[max_evidence:]

        rejected = [
            RejectedEvidence(
                url=item.url,
                title=item.title,
                origin=item.origin,
                stage=PipelineStage.EVIDENCE_RANKING,
                reason=(
                    f"{item.relevance_note} — cut by final ranking cap "
                    f"(rank {rank} of {len(scored)}, top {max_evidence} kept)"
                ),
                score=item.relevance_score,
            )
            for rank, item in enumerate(cut, start=len(kept) + 1)
        ]

        if on_phase:
            on_phase("evidence_ranked", {
                "claim": claim.text,
                "kept": [
                    {
                        "url": item.url,
                        "title": item.title,
                        "score": item.relevance_score,
                        "note": item.relevance_note,
                    }
                    for item in kept
                ],
                "rejectedCount": len(rejected),
            })

        return RankingResult(kept=kept, rejected=rejected)

    def _score(self, evidence: Evidence, claim_embedding) -> tuple[float, str]:

        text = (evidence.content or f"{evidence.title}. {evidence.snippet}")[:2000]

        semantic = self.embeddings.similarity(
            claim_embedding,
            self.embeddings.encode(text),
        )

        semantic = max(0.0, min(semantic, 1.0))

        recency = self._recency_score(evidence.published_at)
        reliability = self._reliability(evidence)

        combined = (
            semantic * self.SEMANTIC_WEIGHT
            + recency * self.RECENCY_WEIGHT
            + reliability * self.RELIABILITY_WEIGHT
        )

        breakdown = (
            f"semantic {semantic:.2f}×{self.SEMANTIC_WEIGHT} + "
            f"recency {recency:.2f}×{self.RECENCY_WEIGHT} + "
            f"reliability {reliability:.2f}×{self.RELIABILITY_WEIGHT} "
            f"= {combined:.2f}"
        )

        return combined, breakdown

    def _recency_score(self, published_at) -> float:

        if published_at is None:
            return 0.5

        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)

        age_days = max((datetime.now(timezone.utc) - published_at).days, 0)

        return math.exp(-age_days / self.RECENCY_HALF_LIFE_DAYS)

    def _reliability(self, evidence: Evidence) -> float:

        if evidence.source_reliability is not None:
            return evidence.source_reliability

        domain = urlparse(evidence.url).netloc.replace("www.", "")

        return self._reliability_by_domain.get(domain, self.DEFAULT_RELIABILITY)

    def _load_domain_reliability(self, source_repository: SourceRepository) -> dict[str, float]:

        try:
            sources = source_repository.list()
        except Exception:
            return {}

        return {
            urlparse(str(source.base_url)).netloc.replace("www.", ""): source.reliability_index
            for source in sources
        }
