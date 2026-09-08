from dataclasses import dataclass, field

from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim, RejectedClaim
from src.services.embeddings.service import EmbeddingService


@dataclass
class ClaimSelectionResult:

    selected: list[Claim]

    rejected: list[RejectedClaim] = field(default_factory=list)


class ClaimSelector:

    def __init__(self, embeddings: EmbeddingService | None = None):

        self.embeddings = embeddings or EmbeddingService()

    def select(
        self,
        claims: list[Claim],
        thresholds: PipelineThresholds | None = None,
    ) -> ClaimSelectionResult:

        thresholds = thresholds or PipelineThresholds()

        if not claims:
            return ClaimSelectionResult(selected=[])

        ordered = sorted(
            claims,
            key=lambda claim: claim.confidence,
            reverse=True,
        )

        selected: list[Claim] = []
        selected_embeddings = []
        rejected: list[RejectedClaim] = []

        for claim in ordered:

            text = claim.text.strip()

            if not text:
                continue

            if len(selected) >= thresholds.max_claims_per_article:
                rejected.append(RejectedClaim(text=claim.text, confidence=claim.confidence, reason="exceeds_max_claims_cap"))
                continue

            embedding = self.embeddings.encode(text)

            if self._is_duplicate(
                embedding,
                selected_embeddings,
                thresholds.claim_dedup_threshold,
            ):
                rejected.append(RejectedClaim(text=claim.text, confidence=claim.confidence, reason="semantic_duplicate"))
                continue

            selected.append(claim)
            selected_embeddings.append(embedding)

        return ClaimSelectionResult(selected=selected, rejected=rejected)

    def _is_duplicate(self, embedding, existing, dedup_threshold: float) -> bool:

        return any(
            self.embeddings.similarity(embedding, other) >= dedup_threshold
            for other in existing
        )
