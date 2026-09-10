"""
Named entity recognition - GLiNER, moved here unchanged from
backend/src/processors/nlp/entities.py's EntityExtractor. The behaviour
is identical; what changed is who owns the model and how a threshold
crosses in (an HTTP request field here, a Python call parameter there -
the same shape, per backend/tests/test_invariants.py's own reasoning
about why passing thresholds per-call doesn't break when it crosses a
process boundary).
"""

from __future__ import annotations

from collections import defaultdict

from gliner import GLiNER

from .config import settings

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

# Fallback only for a caller that omits threshold entirely - in practice
# backend's InferenceClient always forwards the run's actual
# entity_threshold, matching backend/src/config/settings.py's own
# ENTITY_THRESHOLD default so a missing value behaves the same as before.
DEFAULT_THRESHOLD = 0.50


class EntityModel:

    def __init__(self):
        self._model: GLiNER | None = None

    def load(self) -> None:

        if self._model is None:
            self._model = GLiNER.from_pretrained(settings.GLINER_MODEL)

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def extract(
        self,
        text: str,
        threshold: float | None = None,
        labels: list[str] | None = None,
    ) -> dict[str, list[str]]:

        if not text:
            return {}

        predictions = self._model.predict_entities(
            text,
            labels=labels or DEFAULT_LABELS,
            threshold=threshold if threshold is not None else DEFAULT_THRESHOLD,
        )

        entities = defaultdict(set)

        for prediction in predictions:
            entities[prediction["label"]].add(prediction["text"])

        return {
            label: sorted(values)
            for label, values in entities.items()
        }


entity_model = EntityModel()
