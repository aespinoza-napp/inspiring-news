"""
Request/response schemas for the inference API.

Deliberately plain JSON shapes (dicts of floats/strings/lists) rather
than anything backend-specific - this service does not import from
backend/, and backend/src/services/inference_client.py is what
translates between these shapes and backend's own models
(SentimentResult, etc.).
"""

from __future__ import annotations

from pydantic import BaseModel, model_validator


class EntitiesRequest(BaseModel):
    text: str
    threshold: float | None = None
    labels: list[str] | None = None


class EntitiesResponse(BaseModel):
    entities: dict[str, list[str]]


class SentimentRequest(BaseModel):
    text: str


class SentimentResponse(BaseModel):
    label: str
    positive: float
    neutral: float
    negative: float
    polarity: float
    subjectivity: float
    confidence: float
    emotional_intensity: float


class EmbeddingRequest(BaseModel):
    # Exactly one of the two - see the validator below. Single vs. batch
    # are separate fields rather than "always a list" so a single-text
    # caller gets a single vector back, not a list of one.
    text: str | None = None
    texts: list[str] | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "EmbeddingRequest":

        if (self.text is None) == (self.texts is None):
            raise ValueError("Provide exactly one of 'text' or 'texts'.")

        return self


class EmbeddingResponse(BaseModel):
    embedding: list[float] | None = None
    embeddings: list[list[float]] | None = None
    dimension: int


class HealthResponse(BaseModel):
    status: str
    modelsLoaded: dict[str, bool]
