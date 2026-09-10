"""
Sentence embeddings - moved here unchanged from
backend/src/services/embeddings/service.py's EmbeddingService.
`similarity()` did NOT move: it's pure numpy dot-product arithmetic on
two already-computed vectors, needs no model, and stays in backend
(TopicClassifier, EvidenceRanker, etc. call it directly on vectors they
already have - see backend/src/services/embeddings/service.py after
the Phase C refactor).
"""

from __future__ import annotations

from typing import Iterable

from sentence_transformers import SentenceTransformer

from .config import settings


class EmbeddingModel:

    def __init__(self):
        self._model: SentenceTransformer | None = None

    def load(self) -> None:

        if self._model is None:
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def encode(self, text: str) -> list[float]:

        return self._model.encode(
            text,
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).tolist()

    def encode_many(self, texts: Iterable[str]) -> list[list[float]]:

        return self._model.encode(
            list(texts),
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).tolist()

    @property
    def dimension(self) -> int:

        return self._model.get_sentence_embedding_dimension()


embedding_model = EmbeddingModel()
