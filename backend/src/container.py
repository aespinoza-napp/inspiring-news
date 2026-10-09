import threading

from src.config.settings import settings

from src.database.qdrant import QdrantDatabase
from src.repositories.datalake_repository import DataLakeRepository
from src.repositories.vector_repository import VectorRepository
from src.services.admission.admission_filter import AdmissionFilter
from src.services.analysis_service import AnalysisService
from src.services.claim_service import ClaimService
from src.services.enrichment_service import EnrichmentService
from src.services.corrector.text_corrector import TextCorrector
from src.services.fact_checker.fact_checker import FactChecker
from src.services.ingestion_service import IngestionService
from src.services.job_queue import AnalysisJobQueue
from src.services.job_store import JobStore
from src.services.scraper.source_probe import SourceProbe
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
_admission_filter: AdmissionFilter | None = None
_claim_service: ClaimService | None = None
_enrichment_service: EnrichmentService | None = None
_job_queue: AnalysisJobQueue | None = None
_ingestion_service: IngestionService | None = None
_source_probe: SourceProbe | None = None

_source_check_service = None

_graph_client = None
_graph_writer = None
_graph_reader = None

_labelling_batch = None

_reader_index = None

_selection_service = None


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


def get_admission_filter() -> AdmissionFilter:
    """
    Shared admission module: topic, positive impact, duplicates. Shares
    the one VectorRepository with the FactChecker - the duplicate check
    and the internal-evidence lookup read the same collection.
    """

    global _admission_filter

    if _admission_filter is None:
        with _lock:
            if _admission_filter is None:
                _admission_filter = AdmissionFilter(get_vector_repository())

    return _admission_filter


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
                    admission=get_admission_filter(),
                    enrichment_pipeline=get_enrichment_pipeline(),
                    lake=get_datalake_repository() if settings.LAKE_ENABLED else None,
                    graph=get_graph_writer() if settings.GRAPH_ENABLED else None,
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
                from src.services.selection.mission_screen import MissionScreen

                _ingestion_service = IngestionService(
                    sources=SourceRepository().list(),
                    lake=get_datalake_repository(),
                    screen=MissionScreen(),
                )

    return _ingestion_service


def get_selection_service():
    """
    Backs /ingest/rounds: candidate rounds over the ingestion service's
    discovery, the AI selection and the queue. A singleton because an AI
    selection runs in the background and only one may run at a time - the
    model is shared and slow. The rounds themselves are on disk
    (src/services/selection/rounds.py), so a restart loses none.
    """

    global _selection_service

    if _selection_service is None:
        with _lock:
            if _selection_service is None:
                from src.services.selection.selection_service import SelectionService

                _selection_service = SelectionService(ingestion=get_ingestion_service())

    return _selection_service


def get_source_check_service():
    """
    Backs /sources/check. A singleton for the same reason as ingestion:
    the last report is shown when the page is reopened.
    """

    global _source_check_service

    if _source_check_service is None:
        with _lock:
            if _source_check_service is None:
                from src.repositories.source_repository import SourceRepository
                from src.services.scraper.source_check import SourceCheckService

                _source_check_service = SourceCheckService(
                    sources=SourceRepository().list(),
                )

    return _source_check_service



def get_source_probe() -> SourceProbe:
    """
    Backs /scraper/probe. A singleton for the same reason as ingestion:
    the run happens on a background thread, and the page polls this one
    object for it. The last report is read back from the lake on start.
    """

    global _source_probe

    if _source_probe is None:
        with _lock:
            if _source_probe is None:
                from src.repositories.source_repository import SourceRepository
                from src.services.search import SearxngClient

                _source_probe = SourceProbe(
                    sources=SourceRepository().list(),
                    path=settings.LAKE_PATH / "stats" / "source_probe.json",
                    search_client=SearxngClient(),
                )

    return _source_probe


def get_graph_client():
    """
    One Neo4j driver per process - it owns a connection pool. Building it
    does not connect (the first session does), so this is safe with Neo4j
    down; the imports are local for the same reason as the source probe's.
    """

    global _graph_client

    if _graph_client is None:
        with _lock:
            if _graph_client is None:
                from src.database.neo4j_client import GraphClient

                _graph_client = GraphClient(
                    uri=settings.NEO4J_URI,
                    user=settings.NEO4J_USER,
                    password=settings.NEO4J_PASSWORD.get_secret_value(),
                )

    return _graph_client


def get_graph_writer():
    """
    Writes each finished analysis into the graph (AnalysisService's
    `graph`), and backs POST /graph/sync. The source YAMLs are read once,
    here, like ingestion's.
    """

    global _graph_writer

    if _graph_writer is None:
        with _lock:
            if _graph_writer is None:
                from src.repositories.source_repository import SourceRepository
                from src.services.graph.graph_writer import GraphWriter

                _graph_writer = GraphWriter(
                    get_graph_client(),
                    sources=SourceRepository().list(),
                )

    return _graph_writer


def get_graph_reader():

    global _graph_reader

    if _graph_reader is None:
        with _lock:
            if _graph_reader is None:
                from src.services.graph.graph_reader import GraphReader

                _graph_reader = GraphReader(get_graph_client())

    return _graph_reader


def get_labelling_batch():
    """
    Backs /labelling/batch. A singleton like the probe: the batch is built
    on a background thread and the labeller polls this one object for it.
    Borrows the enrichment pipeline's extractor and a ClaimSelector over
    its own EmbeddingService - the same selection the fact-checker makes,
    without opening Qdrant.
    """

    global _labelling_batch

    if _labelling_batch is None:
        with _lock:
            if _labelling_batch is None:
                from src.repositories.source_repository import SourceRepository
                from src.services.embeddings.service import EmbeddingService
                from src.services.fact_checker.claim_selector import ClaimSelector
                from src.services.labelling_batch import LabellingBatch
                from src.services.scraper.extractor import ExtractorService

                sources = SourceRepository().list()
                pipeline = get_enrichment_pipeline()

                _labelling_batch = LabellingBatch(
                    sources=sources,
                    extractor=ExtractorService(sources=sources),
                    enrichment=pipeline,
                    selector=ClaimSelector(EmbeddingService()),
                    claim_extractor=pipeline.claims,
                    # The rounds' own screen: its descriptions are embedded
                    # once for both.
                    screen=get_ingestion_service().screen,
                )

    return _labelling_batch


def get_reader_index():
    """
    Backs /reader/*. A singleton because it *is* a cache: the feed index
    over the exploitation layer, kept in step by file stamps so a request
    reads only what changed (src/services/reader/index.py). Shares the
    lake singleton, so it reads exactly what the pipeline writes. The
    source YAMLs are read once, here, for display names - adding a source
    means restarting, as it does for ingestion.
    """

    global _reader_index

    if _reader_index is None:
        with _lock:
            if _reader_index is None:
                from src.repositories.source_repository import SourceRepository
                from src.services.reader.index import ReaderIndex
                from src.services.reader.views import SourceNames

                _reader_index = ReaderIndex(
                    get_datalake_repository(),
                    SourceNames(SourceRepository().list()),
                )

    return _reader_index
