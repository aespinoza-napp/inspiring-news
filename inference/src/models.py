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
    # Exactly one of the two, as for embeddings. `texts` exists for the
    # claim extractor, which needs every sentence's entities: one request
    # for all of them instead of one per sentence (2026-10-16).
    text: str | None = None
    texts: list[str] | None = None
    threshold: float | None = None
    labels: list[str] | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "EntitiesRequest":

        if (self.text is None) == (self.texts is None):
            raise ValueError("Provide exactly one of 'text' or 'texts'.")

        return self


class EntitiesResponse(BaseModel):
    entities: dict[str, list[str]] | None = None
    entitiesPerText: list[dict[str, list[str]]] | None = None


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


class DecisionRequest(BaseModel):
    # Laya (src/decisions.py). The checkpoint is a built-in name or a
    # fine-tuned folder's name; the questions are Laya's typed questions,
    # passed through as the backend wrote them. Exactly one of state and
    # states: many states share the questions and one batched pass.
    checkpoint: str
    questions: dict[str, dict]
    state: str | dict | list | None = None
    states: list[str | dict | list] | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "DecisionRequest":

        if (self.state is None) == (self.states is None):
            raise ValueError("Provide exactly one of 'state' or 'states'.")

        if not self.questions:
            raise ValueError("Ask at least one question.")

        return self


class DecisionResponse(BaseModel):
    checkpoint: str
    answers: dict[str, dict] | None = None
    answersPerState: list[dict[str, dict]] | None = None
