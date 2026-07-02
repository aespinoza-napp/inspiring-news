from textblob import TextBlob
from typing import List
from src.api.scraper import ScraperAgent
from src.agents.fact_checker import FactChecker
from src.processors.nlp import NLPEngine
from src.models.news import NewsArticle

class NewsIntelligence:
    def __init__(self, db_client):
        self.db = db_client

    async def analyze_sentiment(self, text: str) -> float:
        # Returns score from -1 (negative) to 1 (positive)
        return TextBlob(text).sentiment.polarity

    async def fact_check(self, article: str) -> str:
        # Placeholder for LLM fact-checking logic
        # In production, use LangChain + Google Search Tool
        return "verified"

    async def format_for_social(self, article: str, platform: str) -> str:
        if platform == "instagram":
            return f"📸 NEWS: {article[:100]}... #news #info"
        if platform == "tiktok":
            return f"🎥 Check this out: {article[:50]} #fyp"
        return article

    async def process_and_store(self, article: NewsArticle):
        article.sentiment_score = await self.analyze_sentiment(article.raw_content)
        article.fact_check_status = await self.fact_check(article.raw_content)
        
        # Save to Neo4j
        await self.db.save_news_node(article)


from src.agents.fact_checker import FactChecker
from src.database.local_repository import LocalRepository
from src.models.news import News
from src.processors.nlp import NLPProcessor


class NewsPipeline:

    def __init__(
        self,
        repository: LocalRepository,
    ):

        self.repository = repository

        self.nlp = NLPProcessor()

        self.fact_checker = FactChecker()

    def execute(
        self,
        news: News,
    ) -> News:

        claims = self.nlp.process(
            news.content
        )

        news.claims = claims

        news.fact_checks = [

            self.fact_checker.verify(claim)

            for claim in claims

        ]

        self.repository.save(news)

        return news