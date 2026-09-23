import threading

from src.config.settings import settings

from src.database.qdrant import QdrantDatabase
from src.repositories.datalake_repository import DataLakeRepository
from src.repositories.vector_repository import VectorRepository
from src.services.analysis_service import AnalysisService
from src.services.claim_service import ClaimService
from src.services.enrichment_service import EnrichmentService
from src.services.corrector.text_corrector import TextCorrector
from src.services.fact_checker.fact_checker import FactChecker
from src.services.ingestion_service import IngestionService
from src.services.job_queue import AnalysisJobQueue
from src.services.job_store import JobStore
from src.workflows.enrichment import NewsEnrichmentPipeline

# ---------------------------------------------------------------------
# Everything below is constructed lazily (on first actual use), not at
# import time.
#
# The original reason has narrowed: NewsEnrichmentPipeline/TextCorrector
# used to eagerly load transformer models (GLiNER, the sentiment
# classifier, sentence-transformers) on construction - several seconds
# of real work each, re-paid on every `uvicorn --reload`. Those models
# now live in the inference/ service and are reached over HTTP
# (src/services/inference_client.py), so EntityExtractor,
# SentimentAnalyzer and EmbeddingService are cheap objects wrapping an
# httpx client. What remains genuinely expensive here is
# VectorRepository, which additionally has the QdrantClient
# local-storage lock problem (see get_vector_repository below): eager
# construction meant every reload also raced to grab an exclusive file
# lock. TopicClassifier is the other one worth deferring - it encodes
# every configured TOPICS entry at construction, which is now a burst
# of real HTTP calls rather than local matrix work.
#
# Deferring construction to first use means `uvicorn --reload` restarts
# are near-instant; only the first request that actually needs a given
# service pays its setup cost, once, and it's cached for the rest of
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

# RLock, not Lock: get_analysis_service() acquires this and then, while
# still holding it, calls get_vector_repository()/get_enrichment_pipeline()
# - which also acquire it. A plain Lock isn't reentrant, so that's a
# guaranteed self-deadlock on the very first call (reproduced live: the
# job's "initializing" phase fired, then everything hung forever - no
# "initialized", no timeout, nothing, because the thread was blocked
# waiting on a lock it already held). RLock allows the same thread to
# re-acquire it.
_lock = threading.RLock()

_vector_repository: VectorRepository | None = None
_analysis_service: AnalysisService | None = None
_enrichment_pipeline: NewsEnrichmentPipeline | None = None
_text_corrector: TextCorrector | None = None
_datalake_repository: DataLakeRepository | None = None
_fact_checker: FactChecker | None = None
_claim_service: ClaimService | None = None
_enrichment_service: EnrichmentService | None = None
_job_queue: AnalysisJobQueue | None = None
_ingestion_service: IngestionService | None = None


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


def get_datalake_repository() -> DataLakeRepository:
    """
    Shared handle on the three-layer lake (raw/processed/exploitation).
    Cheap to build (it only ensures directories exist), but a singleton
    anyway so the pipeline that writes records and the endpoints that
    read them always agree on one backend - and so swapping the backend
    for a real database later is a one-line change here rather than at
    every call site.
    """

    global _datalake_repository

    if _datalake_repository is None:
        with _lock:
            if _datalake_repository is None:
                _datalake_repository = DataLakeRepository()

    return _datalake_repository


def get_fact_checker() -> FactChecker:
    """
    Shared FactChecker. A singleton because it owns the VectorRepository
    (single Qdrant client per process) and an EmbeddingService, and
    because /analyze and /verify-claim must run the identical verifier -
    two instances would be two chances to drift.
    """

    global _fact_checker

    if _fact_checker is None:
        with _lock:
            if _fact_checker is None:
                _fact_checker = FactChecker(get_vector_repository())

    return _fact_checker


def get_claim_service() -> ClaimService:
    """
    Backs POST /verify-claim. Lazy for the usual reason: reaching it
    builds the FactChecker, which opens Qdrant.
    """

    global _claim_service

    if _claim_service is None:
        with _lock:
            if _claim_service is None:
                _claim_service = ClaimService(
                    fact_checker=get_fact_checker(),
                    # Shares the enrichment pipeline's EntityExtractor.
                    # This mattered more when that meant sharing a loaded
                    # GLiNER; now they share an inference/ HTTP client
                    # and, more usefully, the same configured labels and
                    # default threshold.
                    entity_extractor=get_enrichment_pipeline().entities,
                )

    return _claim_service


def get_enrichment_service() -> EnrichmentService:
    """
    Backs POST /enrich. Wraps the same NewsEnrichmentPipeline singleton
    the article pipeline uses, so /enrich and /analyze cannot derive
    different things from the same text.
    """

    global _enrichment_service

    if _enrichment_service is None:
        with _lock:
            if _enrichment_service is None:
                _enrichment_service = EnrichmentService(get_enrichment_pipeline())

    return _enrichment_service


def get_analysis_service() -> AnalysisService:

    global _analysis_service

    if _analysis_service is None:
        with _lock:
            if _analysis_service is None:
                _analysis_service = AnalysisService(
                    fact_checker=get_fact_checker(),
                    enrichment_pipeline=get_enrichment_pipeline(),
                    lake=get_datalake_repository() if settings.LAKE_ENABLED else None,
                )

    return _analysis_service


def get_job_queue() -> AnalysisJobQueue:
    """
    Bounds concurrent /analyze/jobs runs (single or batch) at
    settings.ANALYSIS_MAX_CONCURRENCY. Sized from settings here, at
    construction time - not frozen into a class body - so it still
    picks up per-process env/.env values, it just can't change mid-run.
    """

    global _job_queue

    if _job_queue is None:
        with _lock:
            if _job_queue is None:
                _job_queue = AnalysisJobQueue(settings.ANALYSIS_MAX_CONCURRENCY)

    return _job_queue


def get_text_corrector() -> TextCorrector:

    global _text_corrector

    if _text_corrector is None:
        with _lock:
            if _text_corrector is None:
                _text_corrector = TextCorrector()

    return _text_corrector


def get_ingestion_service() -> IngestionService:
    """
    Backs POST /ingest. A singleton so the last run's report survives
    between the POST and the page that shows it. The source YAMLs are read
    once, here: adding a source means restarting, as it always has.
    """

    global _ingestion_service

    if _ingestion_service is None:
        with _lock:
            if _ingestion_service is None:
                from src.repositories.source_repository import SourceRepository

                _ingestion_service = IngestionService(
                    sources=SourceRepository().list(),
                    lake=get_datalake_repository(),
                )

    return _ingestion_service
