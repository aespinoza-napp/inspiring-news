from dataclasses import dataclass, field

from src.config.settings import settings
from src.models.core.claim import Claim, RejectedClaim
from src.services.embeddings.service import EmbeddingService


@dataclass
class ClaimSelectionResult:

    selected: list[Claim]

    rejected: list[RejectedClaim] = field(default_factory=list)


class ClaimSelector:

    MAX_CLAIMS = settings.MAX_CLAIMS_PER_ARTICLE

    DEDUP_THRESHOLD = settings.CLAIM_DEDUP_THRESHOLD

    def __init__(self, embeddings: EmbeddingService | None = None):

        self.embeddings = embeddings or EmbeddingService()

    def select(self, claims: list[Claim]) -> ClaimSelectionResult:

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

            if len(selected) >= self.MAX_CLAIMS:
                rejected.append(RejectedClaim(text=claim.text, confidence=claim.confidence, reason="exceeds_max_claims_cap"))
                continue

            embedding = self.embeddings.encode(text)

            if self._is_duplicate(embedding, selected_embeddings):
                rejected.append(RejectedClaim(text=claim.text, confidence=claim.confidence, reason="semantic_duplicate"))
                continue

            selected.append(claim)
            selected_embeddings.append(embedding)

        return ClaimSelectionResult(selected=selected, rejected=rejected)

    def _is_duplicate(self, embedding, existing) -> bool:

        return any(
            self.embeddings.similarity(embedding, other) >= self.DEDUP_THRESHOLD
            for other in existing
        )
