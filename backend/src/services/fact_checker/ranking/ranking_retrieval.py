import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse

from src.config.settings import settings
from src.models.core.claim import Claim
from src.models.fact_checker.evidence import Evidence, RejectedEvidence
from src.models.fact_checker.pipeline_stage import PipelineStage
from src.repositories.source_repository import SourceRepository
from src.services.embeddings.service import EmbeddingService


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

    def rank(self, claim: Claim, evidence: list[Evidence]) -> RankingResult:

        if not evidence:
            return RankingResult(kept=[])

        claim_embedding = self.embeddings.encode(claim.text)

        scored = [
            item.model_copy(update={
                "relevance_score": self._score(item, claim_embedding),
            })
            for item in evidence
        ]

        scored.sort(key=lambda item: item.relevance_score, reverse=True)

        kept = scored[:settings.MAX_EVIDENCE_PER_CLAIM]
        cut = scored[settings.MAX_EVIDENCE_PER_CLAIM:]

        rejected = [
            RejectedEvidence(
                url=item.url,
                title=item.title,
                origin=item.origin,
                stage=PipelineStage.EVIDENCE_RANKING,
                reason=(
                    f"cut by final ranking cap (rank {rank} of {len(scored)}, "
                    f"top {settings.MAX_EVIDENCE_PER_CLAIM} kept)"
                ),
                score=item.relevance_score,
            )
            for rank, item in enumerate(cut, start=len(kept) + 1)
        ]

        return RankingResult(kept=kept, rejected=rejected)

    def _score(self, evidence: Evidence, claim_embedding) -> float:

        text = (evidence.content or f"{evidence.title}. {evidence.snippet}")[:2000]

        semantic = self.embeddings.similarity(
            claim_embedding,
            self.embeddings.encode(text),
        )

        semantic = max(0.0, min(semantic, 1.0))

        return (
            semantic * self.SEMANTIC_WEIGHT
            + self._recency_score(evidence.published_at) * self.RECENCY_WEIGHT
            + self._reliability(evidence) * self.RELIABILITY_WEIGHT
        )

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
