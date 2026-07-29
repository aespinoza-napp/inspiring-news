from __future__ import annotations

from typing import Iterable

import numpy as np
from sentence_transformers import SentenceTransformer

from src.config.settings import settings


class EmbeddingService:

    _instance = None

    def __new__(cls):

        if cls._instance is None:

            cls._instance = super().__new__(cls)

            cls._instance._model = None

        return cls._instance

    #########################################################

    @property
    def model(self):

        if self._model is None:

            self._model = SentenceTransformer(
                settings.EMBEDDING_MODEL
            )

        return self._model

    #########################################################
    @property
    def model_name(self) -> str:
        return settings.EMBEDDING_MODEL

    #########################################################


    def encode(
        self,
        text: str,
    ) -> np.ndarray:

        return self.model.encode(
            text,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

    #########################################################

    def encode_many(
        self,
        texts: Iterable[str],
    ) -> np.ndarray:

        return self.model.encode(
            list(texts),
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

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
    def dimension(self):

        return self.model.get_sentence_embedding_dimension()