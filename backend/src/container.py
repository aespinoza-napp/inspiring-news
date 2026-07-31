from src.config.settings import settings
from src.models.core.news import News
from src.repositories.local_repository import LocalRepository
from src.processors.nlp.processor import NLPProcessor
from src.agents.fact_checker import FactChecker
from src.workflows.news_pipeline import NewsPipeline
from src.processors.nlp.sentiment import SentimentAnalyzer

repository = LocalRepository(model=News, folder=settings.PROCESSED_PATH)

nlp = NLPProcessor()

fact_checker = FactChecker()

sentiment_analyzer = SentimentAnalyzer(settings)

pipeline = NewsPipeline(
    repository=repository,
    nlp=nlp,
    fact_checker=fact_checker,
    sentiment_analyzer=sentiment_analyzer
)

# ---------------------------------------------------------------------
# Real analyzer/fact-checker pipeline (backs /analyze and /correct) -
# independent of the mock pipeline above, which stays untouched.
#
# vector_repository/real_fact_checker/analysis_service are constructed
# lazily (on first actual use), not at import time. QdrantClient's local
# mode takes an exclusive file lock, and under `uvicorn --reload` this
# module gets re-imported on every file save; opening the lock eagerly
# here meant *every reload* raced to grab it, and a slow-releasing prior
# worker (or literally anything else briefly touching the same storage
# dir) crashed the entire app on import - not just the one feature that
# needed Qdrant. Deferring construction means the app always starts, and
# only a request that actually needs Qdrant can fail if it's briefly busy.
# ---------------------------------------------------------------------

from src.database.qdrant import QdrantDatabase
from src.repositories.vector_repository import VectorRepository
from src.services.analysis_service import AnalysisService
from src.services.corrector.text_corrector import TextCorrector
from src.services.fact_checker.fact_checker import FactChecker as RealFactChecker
from src.services.job_store import JobStore
from src.workflows.enrichment import NewsEnrichmentPipeline

enrichment_pipeline = NewsEnrichmentPipeline(settings)

text_corrector = TextCorrector()

# In-memory, no I/O - safe to construct eagerly, unlike the Qdrant-backed
# services below.
job_store = JobStore()

_vector_repository: VectorRepository | None = None
_analysis_service: AnalysisService | None = None


def get_vector_repository() -> VectorRepository:

    global _vector_repository

    if _vector_repository is None:
        _vector_repository = VectorRepository(QdrantDatabase())

    return _vector_repository


def get_analysis_service() -> AnalysisService:

    global _analysis_service

    if _analysis_service is None:
        _analysis_service = AnalysisService(
            fact_checker=RealFactChecker(get_vector_repository()),
            enrichment_pipeline=enrichment_pipeline,
        )

    return _analysis_service