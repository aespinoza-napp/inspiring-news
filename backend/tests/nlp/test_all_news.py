"""
Enrich every real scraped article under `data/raw` and check the
pipeline survives all of them.

Excluded from the default run by the `slow` marker, not by an
`--ignore` path: it loads the full model stack and enriches nine
articles, which is minutes rather than seconds. Run it with
`./scripts/check.sh slow`.

Two things were wrong with it before, both hidden by that exclusion:

1. It saved into `settings.PROCESSED_PATH` - i.e. straight over the nine
   sample fixtures that are **tracked in git**. Anyone running plain
   `pytest` (forgetting the ignore flag, which is the non-obvious part)
   silently rewrote committed files. This is the same defect CLAUDE.md
   records as fixed for `test_pipeline.py`; it was still live here.
2. Every per-article assertion sat inside a `try/except Exception`,
   which catches `AssertionError` too. Failures were counted into a
   `failed` tally that nothing asserted against, so the only condition
   that could actually fail the test was "not a single article
   processed". It could not detect the thing it was written to detect.
"""

import pytest

from src.config.settings import Settings
from src.models.core.enriched_article import EnrichedArticle
from src.models.core.news import News
from src.repositories.local_repository import LocalRepository
from src.workflows.enrichment import NewsEnrichmentPipeline


@pytest.mark.slow
def test_every_raw_article_survives_enrichment(tmp_path):

    settings = Settings()

    articles = LocalRepository(model=News, folder=settings.RAW_PATH).list()

    if not articles:
        pytest.skip(
            f"No sample articles under {settings.RAW_PATH}; this test "
            "reads real scraped input rather than a fixture."
        )

    pipeline = NewsEnrichmentPipeline(settings)

    # A throwaway directory, never settings.PROCESSED_PATH: those nine
    # files are committed sample data, not scratch space.
    output = LocalRepository(model=EnrichedArticle, folder=tmp_path)

    failures: list[str] = []

    for article in articles:

        # Only genuine pipeline crashes are collected here. Assertions
        # live below, outside the except, so a wrong result fails the
        # test instead of being tallied and ignored.
        try:
            enriched = pipeline.process(article)
        except Exception as exc:
            failures.append(f"{article.id}: {type(exc).__name__}: {exc}")
            continue

        output.save(enriched)

        problems = [
            name
            for name, ok in (
                ("embedding", len(enriched.embedding) > 0),
                ("dimension", len(enriched.embedding) == settings.EMBEDDING_DIMENSION),
                ("keywords", bool(enriched.keywords)),
                ("language", enriched.language in {"en", "es"}),
                ("sentiment", enriched.sentiment.confidence > 0),
                ("quality", 0.0 <= enriched.quality.readability <= 1.0),
                ("body", enriched.body == article.content),
            )
            if not ok
        ]

        if problems:
            failures.append(f"{article.id}: {', '.join(problems)}")

    assert failures == [], (
        f"{len(failures)} of {len(articles)} articles did not survive "
        "enrichment:\n  " + "\n  ".join(failures)
    )

    assert output.count() == len(articles)


@pytest.mark.slow
def test_topics_and_claims_are_found_for_at_least_some_articles(tmp_path):
    """
    Deliberately weaker than per-article: topics and claims are content
    dependent, and a football report legitimately matches none of the
    configured TOPICS. What would be a real regression is the *corpus*
    yielding nothing - that is what a broken lexicon or a dead
    classifier looks like.
    """

    settings = Settings()

    articles = LocalRepository(model=News, folder=settings.RAW_PATH).list()

    if not articles:
        pytest.skip(f"No sample articles under {settings.RAW_PATH}.")

    pipeline = NewsEnrichmentPipeline(settings)

    enriched = [pipeline.process(article) for article in articles]

    assert any(article.topics for article in enriched), (
        "No article in the corpus matched any configured topic."
    )
    assert any(article.claims for article in enriched), (
        "No article in the corpus yielded a single extractable claim."
    )
