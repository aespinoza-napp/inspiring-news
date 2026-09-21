"""
Thin HTTP client for the inference/ service (GLiNER entities, sentiment,
sentence-transformer embeddings) - the same shape as LLMClient
(src/services/llms.py) for the same reason: a heavy AI dependency lives
in another process, reached over HTTP, and this class is the one place
that translates between backend's own models and the wire format.

Unlike LLMClient.complete_json, this does NOT swallow failures uniformly
- error handling is per method, because the three things this wraps
aren't equally tolerant of a missing answer. See EntityExtractor (which
calls .entities() and degrades on failure, mirroring LLMClient) versus
SentimentAnalyzer/EmbeddingService (which call .sentiment()/.encode()/
.encode_many() and let InferenceUnavailable propagate) - both entities.py
and sentiment.py/service.py document why.
"""

from __future__ import annotations

from typing import Any

import httpx

from src.config.settings import settings
from src.services.concurrency import INFERENCE


class InferenceUnavailable(RuntimeError):
    """
    Raised by .sentiment()/.encode()/.encode_many() on any failure -
    unreachable service, timeout, or non-2xx response. Not raised by
    .entities(), which returns {} instead (see EntityExtractor).
    """


class InferenceClient:

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        client: httpx.Client | None = None,
    ):
        self._client = client or httpx.Client(
            base_url=base_url or settings.INFERENCE_URL,
            timeout=timeout or settings.INFERENCE_TIMEOUT,
        )

    def entities(
        self,
        text: str,
        threshold: float | None = None,
        labels: list[str] | None = None,
    ) -> dict[str, list[str]] | None:
        """
        Returns None on any failure rather than raising - the caller
        (EntityExtractor) treats that the same as "no entities found".
        """

        try:
            with INFERENCE.permit():
                response = self._client.post(
                    "/entities",
                    json={"text": text, "threshold": threshold, "labels": labels},
                )
            response.raise_for_status()
        except httpx.HTTPError:
            return None

        return response.json()["entities"]

    def sentiment(self, text: str) -> dict[str, Any]:
        """Raises InferenceUnavailable on any failure - see module docstring."""

        try:
            with INFERENCE.permit():
                response = self._client.post("/sentiment", json={"text": text})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise InferenceUnavailable(f"Sentiment analysis failed: {exc}") from exc

        return response.json()

    def encode(self, text: str) -> tuple[list[float], int]:
        """
        Returns (vector, dimension) - the /embeddings response carries
        both in one call, so EmbeddingService.dimension doesn't need a
        second round-trip just to learn the model's output size.
        Raises InferenceUnavailable on any failure - see module docstring.
        """

        payload = self._embed({"text": text})

        return payload["embedding"], payload["dimension"]

    def encode_many(self, texts: list[str]) -> tuple[list[list[float]], int]:
        """Returns (vectors, dimension). Raises InferenceUnavailable on any failure."""

        payload = self._embed({"texts": texts})

        return payload["embeddings"], payload["dimension"]

    def _embed(self, body: dict) -> dict:

        try:
            # One permit per request, batched or not: /embeddings with 20
            # texts is one call against the ceiling, which is most of why
            # callers were changed to batch rather than loop.
            with INFERENCE.permit():
                response = self._client.post("/embeddings", json=body)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise InferenceUnavailable(f"Embedding request failed: {exc}") from exc

        return response.json()
