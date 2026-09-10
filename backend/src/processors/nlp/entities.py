"""
Named Entity Recognition processor.

GLiNER itself moved to inference/src/entities.py - this class is now an
Adapter over InferenceClient, not a model owner. The public interface
(constructor args, process(text, threshold)) is unchanged on purpose:
every caller (NewsEnrichmentPipeline, ClaimExtractor, ClaimService) only
ever touches .process(), never .model directly, so nothing downstream
needed to change. See backend/src/services/inference_client.py and
docs/decisions/ for why.
"""

from __future__ import annotations

from src.config.settings import settings
from src.services.inference_client import InferenceClient

from .base import BaseProcessor

DEFAULT_LABELS = [
    "person",
    "organization",
    "location",
    "country",
    "city",
    "company",
    "product",
    "event",
]


class EntityExtractor(BaseProcessor):

    def __init__(
        self,
        labels: list[str] | None = None,
        threshold: float | None = None,
        client: InferenceClient | None = None,
    ):

        self._client = client or InferenceClient()

        self.labels = labels or DEFAULT_LABELS

        # Instance default, overridable per call - see process().
        self.threshold = (
            threshold if threshold is not None else settings.ENTITY_THRESHOLD
        )

    def process(
        self,
        text: str,
        threshold: float | None = None,
    ) -> dict[str, list[str]]:

        if not text:
            return {}

        entities = self._client.entities(
            text,
            threshold=threshold if threshold is not None else self.threshold,
            labels=self.labels,
        )

        # Degrade gracefully rather than raise: ClaimExtractor's scoring
        # already treats "no entities" as one weak signal among several
        # (see claims.py's _score), not a hard failure - an inference
        # outage should weaken a sentence's check-worthiness score, not
        # take down the whole enrichment pass. Contrast with
        # SentimentAnalyzer/EmbeddingService, which raise: those feed
        # decisions (admission, duplicate detection) where a silently
        # empty result would corrupt the decision rather than just
        # weaken one signal.
        return entities if entities is not None else {}