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

from textblob import TextBlob

from src.agents.fact_checker import FactChecker
from src.database.repository import NewsRepository
from src.models.news import News
from src.processors.nlp import NLPProcessor


class NewsPipeline:
    """Coordinates the complete news enrichment workflow."""

    def __init__(
        self,
        repository: NewsRepository,
        nlp: NLPProcessor,
        fact_checker: FactChecker,
    ):

        self.repository = repository
        self.nlp = nlp
        self.fact_checker = fact_checker

    def analyze_sentiment(self, text: str) -> float:
        """
        Computes a sentiment score.

        Returns
        -------
        float
            Score between -1 and 1.
        """

        return TextBlob(text).sentiment.polarity

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

        news.sentiment = self.analyze_sentiment(
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