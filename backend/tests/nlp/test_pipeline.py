"""
Smoke test: run the enrichment pipeline over whatever real scraped
article happens to sit in settings.RAW_PATH.

The input here is uncommitted scratch data, so this test can only assert
what holds for *any* article - the pipeline populates every field and the
embedding has the configured shape. It deliberately does not assert that
topics or claims were found: the sample under data/raw is arbitrary (a
football report, say, matches none of the configured TOPICS), and this
test used to fail purely because of which file sorted first. Assertions
about what a *specific* article must yield belong in
tests/test_real_pipeline_integration.py, which uses fixed, committed
input.
"""
import pytest

from src.config.settings import Settings
from src.models.core.enriched_article import EnrichedArticle
from src.models.core.news import News
from src.repositories.local_repository import LocalRepository
from src.workflows.enrichment import NewsEnrichmentPipeline


def test_enrichment_pipeline(tmp_path):

    settings = Settings()

    repository = LocalRepository(
        model=News,
        folder=settings.RAW_PATH,
    )

    articles = repository.list()

    if not articles:
        pytest.skip(
            f"No sample articles under {settings.RAW_PATH}; "
            "this test reads real scraped input rather than a fixture."
        )

    article = articles[0]

    pipeline = NewsEnrichmentPipeline(settings)

    enriched = pipeline.process(article)

    # Save to a throwaway directory, not the tracked sample data under
    # settings.PROCESSED_PATH - this test previously overwrote a
    # committed fixture file on every run.
    LocalRepository(model=EnrichedArticle, folder=tmp_path).save(enriched)

    assert enriched.id == article.id
    assert enriched.body == article.content

    # Regression: keyword extraction was commented out of the pipeline,
    # so this was None - a TypeError here, and a null "keywords" in every
    # API response.
    assert enriched.keywords
    assert len(enriched.keywords) > 0

    assert isinstance(enriched.entities, dict)
    assert isinstance(enriched.topics, list)
    assert isinstance(enriched.claims, list)

    assert enriched.sentiment.confidence > 0
    assert 0.0 <= enriched.quality.readability <= 1.0

    assert enriched.embedding_model
    assert len(enriched.embedding) == enriched.embedding_dimension
    assert enriched.embedding_dimension == settings.EMBEDDING_DIMENSION
