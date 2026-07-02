from src.agents.fact_checker import FactChecker
from src.database.local_repository import LocalRepository
from src.processors.nlp import NLPProcessor
from src.workflows.news_pipeline import NewsPipeline


def test_pipeline(tmp_path, example_news):
    repo = LocalRepository(tmp_path)

    pipeline = NewsPipeline(
        repository=repo,
        nlp=NLPProcessor(),
        fact_checker=FactChecker(),
    )

    result = pipeline.execute(example_news)

    assert len(result.claims) == 3
    assert len(result.fact_checks) == 3
    assert len(repo.list()) == 1