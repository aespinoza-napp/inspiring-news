from datetime import datetime
import tempfile

import pytest

from src.config.settings import settings as live_settings


from src.database.qdrant import QdrantDatabase
from src.repositories.vector_repository import VectorRepository
from src.models.core.news import News
from src.models.core.source import NewsSource, SourceType
from src.repositories.source_repository import SourceRepository

@pytest.fixture
def example_news():
    return News(
        title="NASA discovers water",
        source_id="cnn",
        url="https://cnn.com/news",
        published_at=datetime.now(),
        content=(
            "NASA discovered water on Mars. "
            "Scientists confirmed the discovery. "
            "A fake image circulated online."
        ),
    )

@pytest.fixture
def example_sources():

    sources = SourceRepository().list()

    return sources


@pytest.fixture
def require_inference():
    """
    Skips, rather than fails, when the inference/ service isn't
    reachable at settings.INFERENCE_URL. A test that needs a real GLiNER/
    sentiment/embedding model now needs a real *service* since the
    split, and an unrelated red test in every local run (nobody starts
    `docker compose up inference` or a second `uv run uvicorn` just to
    run `pytest`) trains people to ignore the suite.

    Real-model behavior itself (does the embedding model actually
    cluster similar text, does GLiNER actually find "Apple") is tested
    where the model lives now - inference/tests/. What still needs
    checking from backend/ is that its own classes correctly *use* a
    real inference service - e.g. TopicClassifier's semantic ranking
    end to end, or the EMBEDDING_DIMENSION agreement check.
    """

    skip_unless_inference()


def skip_unless_inference():
    """
    `require_inference`'s check, callable from a fixture of wider scope:
    a module-scoped fixture cannot request a function-scoped one.
    """

    import httpx

    try:
        response = httpx.get(f"{live_settings.INFERENCE_URL}/healthz", timeout=2.0)
        if response.status_code != 200:
            pytest.skip(
                f"inference service at {live_settings.INFERENCE_URL} is not "
                f"warm yet (status {response.status_code})"
            )
    except httpx.HTTPError as exc:
        pytest.skip(f"inference service is not reachable at {live_settings.INFERENCE_URL}: {exc}")


@pytest.fixture
def repository():

    with tempfile.TemporaryDirectory() as path:

        database = QdrantDatabase(
            path=path
        )

        repo = VectorRepository(
            database
        )

        yield repo

        database.client.close()

@pytest.fixture(autouse=True)
def pinned_settings(monkeypatch):
    """
    Pins the *behavioural* settings to the defaults declared in
    `Settings`, ignoring `backend/.env` and the process environment
    alike, so the suite means the same thing on every machine.

    `.env` is deliberately not in git. `test_related_article` needed
    `0.80 <= 0.970 < DUPLICATE_THRESHOLD` and went red for months of
    nobody's mistake when someone tuned that value locally to 0.96.

    Reads `model_fields[...].default` rather than constructing a fresh
    Settings: pydantic-settings reads environment variables even with
    `_env_file=None`, so `DUPLICATE_THRESHOLD=0.5 pytest` would still
    have leaked in - which it did, on the first attempt at this.

    Scoped to thresholds, weights and flags. Infrastructure is left
    exactly as configured: pinning EMBEDDING_MODEL would swap the model
    the suite actually loads (and then disagree with EMBEDDING_DIMENSION),
    and pinning the paths would create a second set of data directories
    beside the ones Settings already made on import.
    """

    pin_settings(monkeypatch)


@pytest.fixture
def list_verifier(monkeypatch):
    """
    The list verifier - one call judging every source - for the tests
    written against it. It was the default until 2026-10-22, when one
    source at a time (VERIFIER_ANSWER=per_source) replaced it by the
    verifier experiment's rule (data/evaluation/experiments/verifier/).
    These tests now name the verifier they test instead of reaching it
    through the default: `pytestmark = pytest.mark.usefixtures("list_verifier")`.
    Function-scoped like `pinned_settings`, and set up after it.
    """

    monkeypatch.setattr(live_settings, "VERIFIER_ANSWER", "full")


def pin_settings(monkeypatch):
    """
    `pinned_settings`' body, callable from a fixture of wider scope with
    its own `pytest.MonkeyPatch.context()`. A module-scoped fixture is set
    up *before* the autouse function-scoped pin, so without this it would
    run under whatever `.env` holds.
    """

    from pydantic_core import PydanticUndefined

    from src.config.thresholds import PipelineThresholds

    fields = type(live_settings).model_fields

    import importlib

    from tests.frozen_settings import FROZEN_SETTINGS

    pinned = {name.upper() for name in PipelineThresholds.model_fields} | {
        "RANKING_SEMANTIC_WEIGHT", "RANKING_LEXICAL_WEIGHT", "RANKING_RECENCY_WEIGHT",
        "RANKING_RELIABILITY_WEIGHT", "RANKING_DEFAULT_RELIABILITY",
        "PERTINENCE_SEMANTIC_WEIGHT", "PERTINENCE_LEXICAL_WEIGHT",
        "CONFIDENCE_LLM_WEIGHT", "CONFIDENCE_EVIDENCE_WEIGHT",
        "EVIDENCE_RECENCY_HALF_LIFE_DAYS",
        "URL_GUARD_ENABLED", "URL_GUARD_ALLOWED_HOSTS", "STORAGE_API_KEY",
        "LAKE_ENABLED",
        # Not a threshold but the choice of their defaults (thresholds.py,
        # FACT_CHECK_PROFILES): left to .env, a dev machine running the app
        # fast turned twelve tests red on 2026-10-22 - every one asserting
        # the thorough pipeline's behaviour.
        "FACT_CHECK_PROFILE",
    }

    for name in pinned:

        field = fields.get(name)

        if field is None or field.default is PydanticUndefined:
            continue

        monkeypatch.setattr(live_settings, name, field.default)

    # The copies those classes took at import, from whatever .env held
    # then - pinning `live_settings` above does not reach them.
    for path, attributes in FROZEN_SETTINGS.items():

        module, cls = path.rsplit(".", 1)
        owner = getattr(importlib.import_module(module), cls)

        for attribute, name in attributes.items():
            monkeypatch.setattr(owner, attribute, fields[name].default)


@pytest.fixture
def draft_store(tmp_path, monkeypatch):
    """
    A DraftStore over tmp_path, installed as the container's singleton, so
    the /drafts routes and any service that asks the container read and
    write here - never settings.DRAFTS_PATH.
    """

    import src.container as container
    from src.services.writer.draft_store import DraftStore

    store = DraftStore(tmp_path / "drafts")

    monkeypatch.setattr(container, "_draft_store", store)

    return store
