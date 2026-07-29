from pathlib import Path

from src.config.settings import Settings
from src.database.local_repository import LocalRepository
from src.workflows.enrichment import NewsEnrichmentPipeline


def test_enrichment_pipeline_repository():

    settings = Settings()
    
    repository = LocalRepository(
        root=settings.STORAGE_PATH,
    )

    pipeline = NewsEnrichmentPipeline(settings)

    processed = 0

    for article in repository:

        enriched = pipeline.process(article)

        assert enriched.title

        assert len(enriched.embedding) > 0

        assert enriched.sentiment.confidence > 0

        processed += 1

    assert processed > 0