"""
Main news processing pipeline.

The pipeline coordinates the execution of all processing stages while
delegating the actual work to specialized components.

Responsibilities
----------------
1. Extract claims and entities.
2. Compute article sentiment.
3. Fact-check every extracted claim.
4. Persist the enriched article.
"""

from src.agents.fact_checker import FactChecker
from src.repositories.repository import NewsRepository
from src.models.core.news import News
from src.processors.nlp import NLPProcessor
from src.processors.nlp.sentiment import SentimentAnalyzer


class NewsPipeline:
    """Coordinates the complete news enrichment workflow."""

    def __init__(
        self,
        repository: NewsRepository,
        nlp: NLPProcessor,
        sentiment_analyzer: SentimentAnalyzer,
        fact_checker: FactChecker,
    ):
        self.repository = repository
        self.nlp = nlp
        self.sentiment_analyzer = sentiment_analyzer
        self.fact_checker = fact_checker

    def execute(self, news: News) -> News:
        """
        Execute the complete enrichment pipeline.

        Parameters
        ----------
        news:
            Raw article.

        Returns
        -------
        News
            Fully processed article.
        """

        # ---------- NLP ----------

        news.claims = self.nlp.process(news.content)

        # ---------- Sentiment ----------

        news.sentiment = self.sentiment_analyzer.analyze(
            news.content
        )

        # ---------- Fact Checking ----------

        news.fact_checks = [
            self.fact_checker.verify(claim)
            for claim in news.claims
        ]

        # ---------- Persistence ----------

        self.repository.save(news)

        return news