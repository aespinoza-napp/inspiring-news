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
# ---------------------------------------------------------------------

from src.database.qdrant import QdrantDatabase
from src.repositories.vector_repository import VectorRepository
from src.services.analysis_service import AnalysisService
from src.services.corrector.text_corrector import TextCorrector
from src.services.fact_checker.fact_checker import FactChecker as RealFactChecker
from src.workflows.enrichment import NewsEnrichmentPipeline

vector_repository = VectorRepository(QdrantDatabase())

real_fact_checker = RealFactChecker(vector_repository)

enrichment_pipeline = NewsEnrichmentPipeline(settings)

analysis_service = AnalysisService(
    fact_checker=real_fact_checker,
    enrichment_pipeline=enrichment_pipeline,
)

text_corrector = TextCorrector()