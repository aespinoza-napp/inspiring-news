from src.config.settings import settings
from src.models.core.news import News
from src.repositories.local_repository import LocalRepository
from src.processors.nlp.processor import NLPProcessor
from src.agents.fact_checker import FactChecker
from src.workflows.news_pipeline import NewsPipeline
from src.processors.nlp.sentiment import SentimentAnalyzer

from src.database.qdrant import QdrantDatabase
from src.repositories.vector_repository import VectorRepository
from src.services.analysis_service import AnalysisService
from src.services.corrector.text_corrector import TextCorrector
from src.services.fact_checker.fact_checker import FactChecker as RealFactChecker
from src.services.job_store import JobStore
from src.workflows.enrichment import NewsEnrichmentPipeline

# ---------------------------------------------------------------------
# Everything below is constructed lazily (on first actual use), not at
# import time. NLPProcessor/NewsEnrichmentPipeline/SentimentAnalyzer/
# TextCorrector all eagerly load transformer models (GLiNER, the
# sentiment classifier, sentence-transformers for embeddings) on
# construction - several seconds of real work each. `uvicorn --reload`
# re-imports this module (in a fresh subprocess) on every file save, so
# building any of this eagerly at module level meant *every single
# reload* re-paid the full model-loading cost before the app could even
# start serving - the dominant cost of local iteration.
#
# VectorRepository additionally has the QdrantClient local-storage lock
# problem (see get_vector_repository below): eager construction meant
# every reload also raced to grab an exclusive file lock.
#
# Deferring construction to first use means `uvicorn --reload` restarts
# are near-instant; only the first request that actually needs a given
# service pays its loading cost, once, and it's cached for the rest of
# that process's life (until the next reload).
# ---------------------------------------------------------------------

repository = LocalRepository(model=News, folder=settings.PROCESSED_PATH)

# In-memory, no I/O - safe to construct eagerly, unlike everything else here.
job_store = JobStore()

_pipeline: NewsPipeline | None = None
_vector_repository: VectorRepository | None = None
_analysis_service: AnalysisService | None = None
_enrichment_pipeline: NewsEnrichmentPipeline | None = None
_text_corrector: TextCorrector | None = None


def get_pipeline() -> NewsPipeline:
    """The old mock pipeline behind /news and /example."""

    global _pipeline

    if _pipeline is None:
        _pipeline = NewsPipeline(
            repository=repository,
            nlp=NLPProcessor(),
            fact_checker=FactChecker(),
            sentiment_analyzer=SentimentAnalyzer(settings),
        )

    return _pipeline


def get_vector_repository() -> VectorRepository:

    global _vector_repository

    if _vector_repository is None:
        _vector_repository = VectorRepository(QdrantDatabase())

    return _vector_repository


def get_enrichment_pipeline() -> NewsEnrichmentPipeline:

    global _enrichment_pipeline

    if _enrichment_pipeline is None:
        _enrichment_pipeline = NewsEnrichmentPipeline(settings)

    return _enrichment_pipeline


def get_analysis_service() -> AnalysisService:

    global _analysis_service

    if _analysis_service is None:
        _analysis_service = AnalysisService(
            fact_checker=RealFactChecker(get_vector_repository()),
            enrichment_pipeline=get_enrichment_pipeline(),
        )

    return _analysis_service


def get_text_corrector() -> TextCorrector:

    global _text_corrector

    if _text_corrector is None:
        _text_corrector = TextCorrector()

    return _text_corrector
