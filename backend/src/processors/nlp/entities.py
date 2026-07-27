"""
Named Entity Recognition processor.

Current implementation
----------------------
- GLiNER-small-v2.1
- multilingual
- CPU friendly

Future implementations
----------------------
- Fine-tuned GLiNER
- Ensemble with LLM
"""

from __future__ import annotations

from collections import defaultdict

from gliner import GLiNER

from .base import BaseProcessor

#from src.config.topics import TOPICS

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

    _model = None

    def __init__(
        self,
        labels: list[str] | None = None,
        threshold: float = 0.5,
        model_name: str = "urchade/gliner_small-v2.1",
    ):

        if EntityExtractor._model is None:
            EntityExtractor._model = GLiNER.from_pretrained(model_name)

        self.model = EntityExtractor._model

        self.labels = labels or DEFAULT_LABELS

        self.threshold = threshold

    def process(self, text: str) -> dict[str, list[str]]:

        if not text:
            return {}

        predictions = self.model.predict_entities(
            text,
            labels=self.labels,
            threshold=self.threshold,
        )

        entities = defaultdict(set)

        for prediction in predictions:
            entities[prediction["label"]].add(
                prediction["text"]
            )

        return {
            label: sorted(values)
            for label, values in entities.items()
        }