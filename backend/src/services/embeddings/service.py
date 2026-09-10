"""
The sentence-transformer model itself moved to inference/src/embeddings.py
- this class is now an Adapter over InferenceClient. `similarity()` did
NOT move: it's pure numpy dot-product arithmetic on two already-computed
vectors, needs no model, and every caller (TopicClassifier,
EvidenceRanker, VectorRetriever, ...) still calls it directly on
vectors they already have.

The `__new__`-based process-wide singleton stays too - one shared
InferenceClient/httpx connection pool per process is still worth having,
even though there's no model weight to avoid reloading anymore.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np

from src.config.settings import settings
from src.services.inference_client import InferenceClient


class EmbeddingService:

    _instance = None

    def __new__(cls):

        if cls._instance is None:

            cls._instance = super().__new__(cls)

            cls._instance._client = InferenceClient()

            cls._instance._dimension = None

        return cls._instance

    #########################################################
    @property
    def model_name(self) -> str:
        return settings.EMBEDDING_MODEL

    #########################################################

    def encode(
        self,
        text: str,
    ) -> np.ndarray:
        """
        Raises InferenceUnavailable (propagated from InferenceClient) on
        failure. Duplicate detection, evidence ranking and topic
        classification all feed on this vector - a silently missing or
        zeroed embedding would corrupt one of those decisions rather
        than just weaken a signal, so this does not degrade the way
        EntityExtractor does.
        """

        vector, dimension = self._client.encode(text)

        self._dimension = dimension

        return np.array(vector)

    #########################################################

    def encode_many(
        self,
        texts: Iterable[str],
    ) -> np.ndarray:

        vectors, dimension = self._client.encode_many(list(texts))

        self._dimension = dimension

        return np.array(vectors)

    #########################################################

    def similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray,
    ) -> float:

        return float(
            np.dot(
                embedding1,
                embedding2,
            )
        )

    #########################################################

    @property
    def dimension(self) -> int:
        """
        Cached from the last encode()/encode_many() call rather than a
        dedicated round-trip - VectorRepository checks this on every
        collection-size verification, and this service has no model
        loaded locally to ask directly anymore. Triggers one real call
        if nothing has been encoded yet this process.
        """

        if self._dimension is None:
            self.encode("dimension probe")

        return self._dimension