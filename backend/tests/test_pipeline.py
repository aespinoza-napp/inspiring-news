from src.agents.fact_checker import FactChecker
from src.database.local_repository import LocalRepository
from src.processors.nlp.processor import NLPProcessor
from src.workflows.news_pipeline import NewsPipeline
from src.processors.nlp.sentiment import SentimentAnalyzer

def test_pipeline(tmp_path, example_news):
    repo = LocalRepository(tmp_path)

    pipeline = NewsPipeline(
        repository=repo,
        nlp=NLPProcessor(),
        fact_checker=FactChecker(),
        sentiment_analyzer=SentimentAnalyzer()
    )

    result = pipeline.execute(example_news)

    assert len(result.claims) == 3
    assert len(result.fact_checks) == 3
    assert len(repo.list()) == 1