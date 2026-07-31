from src.config.settings import Settings
from src.models.core.news import News
from src.models.core.enriched_article import EnrichedArticle
from src.repositories.local_repository import LocalRepository
from src.workflows.enrichment import NewsEnrichmentPipeline


def test_enrichment_pipeline_all():

    settings = Settings()

    raw_repository = LocalRepository(
        model=News,
        folder=settings.RAW_PATH,
    )

    processed_repository = LocalRepository(
        model=EnrichedArticle,
        folder=settings.PROCESSED_PATH,
    )

    pipeline = NewsEnrichmentPipeline(settings)

    articles = raw_repository.list()

    assert len(articles) > 0, "No raw articles found."

    processed = 0
    failed = 0

    for article in articles:

        try:

            enriched = pipeline.process(article)

            processed_repository.save(enriched)

            print()
            print("=" * 80)
            print(enriched.title)
            print("=" * 80)

            print(f"Keywords : {len(enriched.keywords)}")
            print(f"Entities : {len(enriched.entities)}")
            print(f"Topics   : {len(enriched.topics)}")
            print(f"Claims   : {len(enriched.claims)}")
            print(f"Embedding: {len(enriched.embedding)}")

            assert len(enriched.embedding) > 0
            assert len(enriched.keywords) > 0
            assert len(enriched.claims) > 0
            assert len(enriched.topics) > 0
            assert enriched.sentiment.confidence > 0
            assert enriched.quality.readability >= 0

            processed += 1

        except Exception as exc:

            failed += 1

            print()
            print("=" * 80)
            print(f"FAILED: {article.title}")
            print(exc)
            print("=" * 80)

    print()
    print("=" * 80)
    print("Pipeline summary")
    print("=" * 80)
    print(f"Raw articles : {len(articles)}")
    print(f"Processed    : {processed}")
    print(f"Failed       : {failed}")

    assert processed > 0
    assert processed + failed == len(articles)


if __name__ == "__main__":
    test_enrichment_pipeline_all()