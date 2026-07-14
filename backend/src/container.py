from src.config import settings
from src.database.local_repository import LocalRepository
from src.processors.nlp import NLPProcessor
from src.agents.fact_checker import FactChecker
from src.workflows.news_pipeline import NewsPipeline
from src.processors.sentiment_analysis import SentimentAnalyzer

repository = LocalRepository(settings.STORAGE_PATH)

nlp = NLPProcessor()

fact_checker = FactChecker()

pipeline = NewsPipeline(
    repository=repository,
    nlp=nlp,
    fact_checker=fact_checker,
    sentiment_analyzer=SentimentAnalyzer()
)