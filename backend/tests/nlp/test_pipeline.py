from pathlib import Path

from src.config.settings import Settings
from src.database.local_repository import LocalRepository
from src.workflows.enrichment import NewsEnrichmentPipeline
from src.models.news import News
from src.models.enriched_article import EnrichedArticle


def test_enrichment_pipeline():

    settings = Settings()

    # Look to the repository for a news article to enrich
    repository = LocalRepository(
        model=News,
        folder=settings.RAW_PATH,
    )

    article = repository.list()[0]

    pipeline = NewsEnrichmentPipeline(settings)

    # Save to the repository the enriched article
    enriched = pipeline.process(article)

    repository_to_save = LocalRepository(
        model=EnrichedArticle,
        folder=settings.PROCESSED_PATH,
    )
    repository_to_save.save(enriched)

    print("\n\n\n")
    print(enriched)
    print()

    print("=" * 80)
    print(enriched.title)
    print("=" * 80)

    print("\nKeywords")
    print(enriched.keywords)

    print("\nEntities")
    print(enriched.entities)

    print("\nTopics")
    print(enriched.topics)

    print("\nClaims")
    for claim in enriched.claims:
        print("-", claim.text)

    print("\nSentiment")
    print(enriched.sentiment)

    print("\nQuality")
    print(enriched.quality)

    print("\nEmbedding dimension")
    print(len(enriched.embedding))

    #######################################################

    #assert enriched.title

    #assert enriched.body

    assert len(enriched.embedding) > 0

    assert len(enriched.keywords) > 0

    #assert isinstance(
    #    enriched.entities,
    #    dict,
    #)

    assert len(enriched.claims) > 0

    assert len(enriched.topics) > 0

    assert enriched.sentiment.confidence > 0

    assert enriched.quality.readability >= 0

test_enrichment_pipeline()