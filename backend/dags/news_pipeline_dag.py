"""
Airflow DAG for scheduled news ingestion.

The DAG is intentionally lightweight. It orchestrates the execution of the
business logic but does not contain any processing itself.

Workflow
--------
Scrape articles
        │
        ▼
Process each article through NewsPipeline
        │
        ▼
Persist enriched article
"""

from datetime import datetime

from airflow.decorators import dag, task

from src.agents.scraper import ScraperAgent
from src.container import pipeline


@dag(
    dag_id="news_pipeline",
    description="Scrape, enrich and store news articles",
    schedule="@hourly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["news", "nlp", "fact-check"],
)
def news_pipeline_dag():
    """
    Main DAG.

    Every hour:

        1. Scrape articles.
        2. Process every article.
        3. Store the results.
    """

    @task
    def scrape():
        """
        Fetch latest news articles.

        Returns
        -------
        list[News]
        """

        scraper = ScraperAgent()

        return scraper.fetch_latest()


    @task
    def process(article):
        """
        Execute the complete enrichment pipeline.
        """

        pipeline.execute(article)

        return article.id


    articles = scrape()

    # Airflow 2.3+ Dynamic Task Mapping
    process.expand(article=articles)


dag = news_pipeline_dag()