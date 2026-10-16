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

import re
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

# GLiNER reads at most 384 tokens of a text (gliner_small's max_len) and
# drops the rest with nothing but a UserWarning. A whole article went
# through it in one piece: measured 2026-10-16 on a 5,700-character
# sample, "Sentence of length 1069 has been truncated to 384", and 5
# entities found where its sentences, read one by one, hold 52. So a
# long text is read in sentence-bounded chunks, every chunk in one
# batched call. 250 words, not 384: GLiNER counts punctuation as tokens,
# about 1.2 per word in prose.
CHUNK_WORDS = 250

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def chunks(text: str) -> list[str]:
    """`text` in pieces of at most CHUNK_WORDS words, cut at sentences."""

    if len(text.split()) <= CHUNK_WORDS:
        return [text]

    pieces: list[str] = []
    current: list[str] = []
    count = 0

    for sentence in _SENTENCE_END.split(text):

        words = sentence.split()

        if not words:
            continue

        if current and count + len(words) > CHUNK_WORDS:
            pieces.append(" ".join(current))
            current, count = [], 0

        # A "sentence" longer than a chunk (a list, a table flattened to
        # text) is cut by words rather than left to be truncated.
        if len(words) > CHUNK_WORDS:
            pieces.extend(
                " ".join(words[i:i + CHUNK_WORDS])
                for i in range(0, len(words), CHUNK_WORDS)
            )
            continue

        current.append(sentence)
        count += len(words)

    if current:
        pieces.append(" ".join(current))

    return pieces


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

        return self.extract_many([text], threshold, labels)[0]

    def extract_many(
        self,
        texts: list[str],
        threshold: float | None = None,
        labels: list[str] | None = None,
    ) -> list[dict[str, list[str]]]:
        """
        Each text's entities, every chunk of every text in one batched
        call. A text of one chunk gets exactly what predict_entities gave
        it (that method is `inference([text])`); measured on 40 sentences,
        batched and one-by-one found the same entities in all 40, in 1.7 s
        against 2.5 s.
        """

        pieces: list[str] = []
        owners: list[int] = []

        for index, text in enumerate(texts):
            if text:
                for piece in chunks(text):
                    pieces.append(piece)
                    owners.append(index)

        found: list[defaultdict] = [defaultdict(set) for _ in texts]

        if pieces:

            predictions = self._model.inference(
                pieces,
                labels=labels or DEFAULT_LABELS,
                threshold=threshold if threshold is not None else DEFAULT_THRESHOLD,
            )

            for owner, piece_predictions in zip(owners, predictions):
                for prediction in piece_predictions:
                    found[owner][prediction["label"]].add(prediction["text"])

        return [
            {label: sorted(values) for label, values in entities.items()}
            for entities in found
        ]


entity_model = EntityModel()
