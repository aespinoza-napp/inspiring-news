"""
The inference service: a dumb model server for the three transformer
models backend/ used to load in-process (GLiNER, the sentiment
classifier, sentence-transformers embeddings). It knows nothing about
TOPICS, PipelineThresholds, or any admission/scoring decision - that
logic stays in backend/, which calls this over HTTP the same way it
already calls Ollama through LLMClient (backend/src/services/llms.py).

No __init__.py anywhere, same convention as backend/src - see the
Dockerfile for how this gets imported from the working directory.
"""

from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from logging import getLogger

from fastapi import Depends, FastAPI, HTTPException

from .embeddings import embedding_model
from .entities import entity_model
from .models import (
    EmbeddingRequest,
    EmbeddingResponse,
    EntitiesRequest,
    EntitiesResponse,
    HealthResponse,
    SentimentRequest,
    SentimentResponse,
)
from .sentiment import sentiment_model

logger = getLogger(__name__)

# Set once all three models have loaded. A threading.Event, not a plain
# bool: it's read from request-handling threads and written from the
# warm-up thread below.
_warm = threading.Event()


def _load_models() -> None:
    """
    Runs in a background thread, started from the lifespan handler
    below - NOT awaited before uvicorn starts accepting connections.
    Blocking startup on this would mean a slow/cold model download
    (several GB across three models on a fresh `model-cache` volume)
    delays the container from listening at all, which is worse for
    Compose's healthcheck than serving a clear 503 "not ready yet" from
    a process that is already up and responsive.
    """

    try:
        entity_model.load()
        sentiment_model.load()
        embedding_model.load()
    except Exception:
        logger.exception("Failed to warm up one or more inference models")
        raise
    finally:
        # Set even on failure: an inference service stuck reporting
        # "warming up" forever when a model genuinely failed to load is
        # worse than one whose /healthz call reveals which model didn't
        # come up, via modelsLoaded below.
        _warm.set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=_load_models, daemon=True, name="model-warmup").start()
    yield


app = FastAPI(title="inspiring-news inference", lifespan=lifespan)


def _models_loaded() -> dict[str, bool]:

    return {
        "entities": entity_model.loaded,
        "sentiment": sentiment_model.loaded,
        "embeddings": embedding_model.loaded,
    }


def require_warm() -> None:
    """
    FastAPI dependency guarding every inference route: without this, a
    request arriving during warm-up would block inside the route handler
    for however long the model load takes, rather than getting an
    immediate, honest "not ready" - the same distinction /healthz makes.
    """

    if not _warm.is_set() or not all(_models_loaded().values()):
        raise HTTPException(
            status_code=503,
            detail={"status": "warming_up", "modelsLoaded": _models_loaded()},
        )


@app.get("/healthz", response_model=HealthResponse)
def healthz():
    """
    200 only once every model is actually loaded - not merely "the
    process started". This is what lets docker-compose.yml's backend
    service use `depends_on: inference: condition: service_healthy` and
    turn "first request after boot is slow/racy" (the old in-process
    lazy-loading behaviour) into "the container isn't marked ready until
    it's warm".
    """

    loaded = _models_loaded()

    if not _warm.is_set() or not all(loaded.values()):
        raise HTTPException(
            status_code=503,
            detail={"status": "warming_up", "modelsLoaded": loaded},
        )

    return HealthResponse(status="ok", modelsLoaded=loaded)


@app.post("/entities", response_model=EntitiesResponse, dependencies=[Depends(require_warm)])
def entities(request: EntitiesRequest):

    return EntitiesResponse(
        entities=entity_model.extract(request.text, request.threshold, request.labels)
    )


@app.post("/sentiment", response_model=SentimentResponse, dependencies=[Depends(require_warm)])
def sentiment(request: SentimentRequest):

    result = sentiment_model.analyze(request.text)

    return SentimentResponse(
        label=result.label,
        positive=result.positive,
        neutral=result.neutral,
        negative=result.negative,
        polarity=result.polarity,
        subjectivity=result.subjectivity,
        confidence=result.confidence,
        emotional_intensity=result.emotional_intensity,
    )


@app.post("/embeddings", response_model=EmbeddingResponse, dependencies=[Depends(require_warm)])
def embeddings(request: EmbeddingRequest):

    if request.texts is not None:
        return EmbeddingResponse(
            embeddings=embedding_model.encode_many(request.texts),
            dimension=embedding_model.dimension,
        )

    return EmbeddingResponse(
        embedding=embedding_model.encode(request.text),
        dimension=embedding_model.dimension,
    )
