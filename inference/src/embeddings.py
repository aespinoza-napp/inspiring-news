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
        """
        Every text's vector, in input order. Batched by length rather than
        by count (config.py, EMBEDDING_BATCH_TOKENS): on a CPU a batch
        costs what its longest text costs times its size, so short texts
        share one and a long page goes alone.
        """

        texts = list(texts)
        vectors: list[list[float] | None] = [None] * len(texts)

        for batch in self._batches(texts):
            encoded = self._model.encode(
                [texts[index] for index in batch],
                batch_size=len(batch),
                normalize_embeddings=True,
                convert_to_numpy=True,
            ).tolist()
            for index, vector in zip(batch, encoded):
                vectors[index] = vector

        return vectors

    def _batches(self, texts: list[str]) -> list[list[int]]:
        """Indices of `texts`, shortest first, grouped within the token budget."""

        budget = settings.EMBEDDING_BATCH_TOKENS
        cap = max(1, settings.EMBEDDING_BATCH_SIZE)

        if budget <= 0:
            return [[index] for index in range(len(texts))]

        lengths = [self._tokens(text) for text in texts]

        batches: list[list[int]] = []
        batch: list[int] = []

        for index in sorted(range(len(texts)), key=lambda i: lengths[i]):

            # Sorted, so this text is the batch's longest: padded, the
            # batch would cost its length times the batch's size.
            if batch and (lengths[index] * (len(batch) + 1) > budget or len(batch) >= cap):
                batches.append(batch)
                batch = []

            batch.append(index)

        if batch:
            batches.append(batch)

        return batches

    def _tokens(self, text: str) -> int:

        tokenizer = getattr(self._model, "tokenizer", None)

        if tokenizer is None:
            # Roughly four characters a token, for a model without one.
            return max(1, len(text) // 4)

        tokens = len(tokenizer(text, add_special_tokens=True, truncation=False)["input_ids"])

        # The model reads no further than this; a longer text costs no more.
        limit = getattr(self._model, "max_seq_length", None)

        return min(tokens, limit) if isinstance(limit, int) and limit > 0 else tokens

    @property
    def dimension(self) -> int:

        return self._model.get_sentence_embedding_dimension()


embedding_model = EmbeddingModel()
