import threading

from src.config.settings import settings

from src.database.qdrant import QdrantDatabase
from src.repositories.vector_repository import VectorRepository
from src.services.analysis_service import AnalysisService
from src.services.corrector.text_corrector import TextCorrector
from src.services.fact_checker.fact_checker import FactChecker
from src.services.job_store import JobStore
from src.workflows.enrichment import NewsEnrichmentPipeline

# ---------------------------------------------------------------------
# Everything below is constructed lazily (on first actual use), not at
# import time. NewsEnrichmentPipeline/TextCorrector both eagerly load
# transformer models (GLiNER, the sentiment classifier, sentence-
# transformers for embeddings) on construction - several seconds of
# real work each. `uvicorn --reload` re-imports this module (in a fresh
# subprocess) on every file save, so building any of this eagerly at
# module level meant *every single reload* re-paid the full model-
# loading cost before the app could even start serving - the dominant
# cost of local iteration.
#
# VectorRepository additionally has the QdrantClient local-storage lock
# problem (see get_vector_repository below): eager construction meant
# every reload also raced to grab an exclusive file lock.
#
# Deferring construction to first use means `uvicorn --reload` restarts
# are near-instant; only the first request that actually needs a given
# service pays its loading cost, once, and it's cached for the rest of
# that process's life (until the next reload).
#
# The lazy-init checks below are guarded by a lock (double-checked
# locking): /analyze/jobs runs each request in FastAPI's background
# threadpool, so two requests arriving close together (e.g. the
# frontend's two near-simultaneous POSTs for the same URL, which
# React 18 dev-mode Strict Mode's double-effect-invoke produces) can
# both observe "not built yet" and race to construct a service at the
# same time. For VectorRepository specifically, that meant two threads
# racing to open the *same* exclusive-lock Qdrant storage path
# concurrently - one would win, the other would fail with "already
# accessed by another instance", even though only one process was
# ever involved. Reproduced live: two jobs created ~0ms apart, one
# failed on exactly that error while the other succeeded.
# ---------------------------------------------------------------------

# In-memory, no I/O - safe to construct eagerly, unlike everything below.
job_store = JobStore()

_lock = threading.Lock()

_vector_repository: VectorRepository | None = None
_analysis_service: AnalysisService | None = None
_enrichment_pipeline: NewsEnrichmentPipeline | None = None
_text_corrector: TextCorrector | None = None


def get_vector_repository() -> VectorRepository:

    global _vector_repository

    if _vector_repository is None:
        with _lock:
            if _vector_repository is None:
                _vector_repository = VectorRepository(QdrantDatabase())

    return _vector_repository


def get_enrichment_pipeline() -> NewsEnrichmentPipeline:

    global _enrichment_pipeline

    if _enrichment_pipeline is None:
        with _lock:
            if _enrichment_pipeline is None:
                _enrichment_pipeline = NewsEnrichmentPipeline(settings)

    return _enrichment_pipeline


def get_analysis_service() -> AnalysisService:

    global _analysis_service

    if _analysis_service is None:
        with _lock:
            if _analysis_service is None:
                _analysis_service = AnalysisService(
                    fact_checker=FactChecker(get_vector_repository()),
                    enrichment_pipeline=get_enrichment_pipeline(),
                )

    return _analysis_service


def get_text_corrector() -> TextCorrector:

    global _text_corrector

    if _text_corrector is None:
        with _lock:
            if _text_corrector is None:
                _text_corrector = TextCorrector()

    return _text_corrector
