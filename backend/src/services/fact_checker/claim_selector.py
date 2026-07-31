from src.config.settings import settings
from src.models.core.claim import Claim
from src.services.embeddings.service import EmbeddingService


class ClaimSelector:

    MAX_CLAIMS = settings.MAX_CLAIMS_PER_ARTICLE

    DEDUP_THRESHOLD = settings.CLAIM_DEDUP_THRESHOLD

    def __init__(self, embeddings: EmbeddingService | None = None):

        self.embeddings = embeddings or EmbeddingService()

    def select(self, claims: list[Claim]) -> list[Claim]:

        if not claims:
            return []

        ordered = sorted(
            claims,
            key=lambda claim: claim.confidence,
            reverse=True,
        )

        selected: list[Claim] = []
        selected_embeddings = []

        for claim in ordered:

            if len(selected) >= self.MAX_CLAIMS:
                break

            text = claim.text.strip()

            if not text:
                continue

            embedding = self.embeddings.encode(text)

            if self._is_duplicate(embedding, selected_embeddings):
                continue

            selected.append(claim)
            selected_embeddings.append(embedding)

        return selected

    def _is_duplicate(self, embedding, existing) -> bool:

        return any(
            self.embeddings.similarity(embedding, other) >= self.DEDUP_THRESHOLD
            for other in existing
        )
