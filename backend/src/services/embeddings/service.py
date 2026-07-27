from __future__ import annotations

from typing import Iterable

import numpy as np
from sentence_transformers import SentenceTransformer


DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class EmbeddingService:
    """
    Singleton service used across the application.

    Used by:
        - Topic classifier
        - Duplicate detector
        - RAG
        - Search
        - Recommendation engine
    """

    _instance = None

    def __new__(
        cls,
        model_name: str = DEFAULT_MODEL,
    ):

        if cls._instance is None:

            cls._instance = super().__new__(cls)

            cls._instance._model = SentenceTransformer(
                model_name
            )

        return cls._instance

    def encode(self, text: str) -> np.ndarray:

        return self._model.encode(
            text,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

    def encode_many(
        self,
        texts: Iterable[str],
    ) -> np.ndarray:

        return self._model.encode(
            list(texts),
            normalize_embeddings=True,
            convert_to_numpy=True,
        )