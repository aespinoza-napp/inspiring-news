"""
End-to-end test of the real pipeline wiring: a real News object goes
through the real NewsEnrichmentPipeline (real GLiNER/topic-classifier/
sentiment/quality/embedding models, no mocks), then the real
ValidationPipeline (backed by a temporary on-disk Qdrant, per the shared
`repository` fixture), then the real ClaimSelector.

Every other test in this suite fakes at least one of those boundaries
(existing fact-checker orchestrator tests start from a pre-built
EnrichedArticle via tests/factories.py, bypassing enrichment entirely).
This is the one place that exercises the actual handoff between them
with fixed, offline input - no live network, no SearXNG, no LLM, so it
stays fast and deterministic, but it would have caught e.g. a field the
enrichment pipeline stops populating that validation or claim selection
still expects.
"""
from src.config.settings import settings
from src.config.thresholds import PipelineThresholds
from src.models.storage.lineage import DataLayer
from src.repositories.datalake_repository import DataLakeRepository
from src.repositories.lake_backend import JsonFileLakeBackend
from src.models.core.enriched_article import EnrichedArticle
from src.models.core.news import News
from src.models.fact_checker.fact_check import Verdict
from src.models.fact_checker.fact_check_report import FactCheckReport
from src.services.fact_checker.claim_selector import ClaimSelector
from src.services.fact_checker.validation_pipeline import ValidationPipeline
from src.workflows.enrichment import NewsEnrichmentPipeline

ARTICLE_BODY = """
Researchers at a major university hospital announced a breakthrough
treatment for a rare form of childhood leukemia. The clinical trial,
which enrolled 120 patients over three years, reported a 94% remission
rate, far exceeding the previous standard of care.

Dr. Elena Vasquez, who led the study, said the therapy retrains the
immune system to recognize cancer cells without the severe side effects
of traditional chemotherapy. The findings were published in a leading
medical journal and confirmed by two independent research teams.

Health officials welcomed the results and said the treatment could
become widely available within two years, offering renewed hope to
thousands of families affected by the disease every year.
"""


def make_news() -> News:

    return News(
        source_id="test-source",
        url="https://example.com/medical-breakthrough",
        title="New leukemia treatment shows 94% remission rate in trial",
        content=ARTICLE_BODY,
    )


def test_real_enrichment_feeds_real_validation_and_claim_selection(repository):

    pipeline = NewsEnrichmentPipeline(settings)
    validation = ValidationPipeline(repository)
    selector = ClaimSelector()

    article = pipeline.process(make_news())

    # The enrichment contract every downstream stage relies on.
    assert article.id
    assert article.body == ARTICLE_BODY
    assert article.entities  # GLiNER should find at least one named entity
    assert article.sentiment is not None
    assert article.quality is not None
    assert len(article.embedding) == article.embedding_dimension == settings.EMBEDDING_DIMENSION

    # A real, positive, on-topic medical story with concrete facts
    # (a named researcher, a percentage, a patient count, "published",
    # "announced") should clear the admission gate and yield checkable
    # claims - this is the scenario the whole system exists for.
    result = validation.validate(article)

    assert result.topic_ok is True
    assert result.duplicate is False

    selection = selector.select(article.claims or [])

    assert len(selection.selected) > 0
    assert len(selection.selected) <= PipelineThresholds().max_claims_per_article

    # Every extracted claim's entities were themselves drawn from the
    # same GLiNER pass - sanity-check the shape survives the round trip.
    for claim in selection.selected:
        assert isinstance(claim.text, str) and claim.text.strip()
        assert 0.0 <= claim.confidence <= 1.0


def test_real_enrichment_output_survives_the_round_trip_into_all_three_layers(tmp_path):
    """
    The persist stage is the only place a real EnrichedArticle is
    serialised whole and read back. Faked articles (tests/factories.py)
    have tidy values; a real one has numpy-derived floats, a 1024-float
    embedding, GLiNER entity dicts and YAKE keywords. This is the test
    that would catch one of those failing to survive model_dump/JSON.
    """

    news = make_news()

    article = NewsEnrichmentPipeline(settings).process(news)

    report = FactCheckReport(
        article_id=article.id,
        validation_passed=True,
        topic_ok=True,
        positive_ok=True,
        duplicate=False,
        claims_total=len(article.claims or []),
        claims_selected=0,
        overall_verdict=Verdict.UNVERIFIED,
    )

    lake = DataLakeRepository(backend=JsonFileLakeBackend(tmp_path))

    run = lake.start_run(news.url)

    written = lake.persist_all(run, news, article, report)

    # Layer 1 holds the untouched fetch.
    raw = lake.get(DataLayer.RAW, written.raw_record_id)
    assert raw["article"]["content"] == ARTICLE_BODY

    # Layer 2 round-trips the full enrichment, embedding included, and
    # re-validates as an EnrichedArticle.
    processed = lake.get(DataLayer.PROCESSED, written.processed_record_id)
    restored = EnrichedArticle.model_validate(processed["article"])

    assert restored.id == article.id
    assert restored.keywords == article.keywords
    assert restored.entities == article.entities
    assert len(restored.embedding) == settings.EMBEDDING_DIMENSION
    assert restored.sentiment.label == article.sentiment.label
    assert restored.quality.readability == article.quality.readability

    # Layer 3 is the flat serving document - no embedding, decision made.
    exploitation = lake.get(DataLayer.EXPLOITATION, written.exploitation_record_id)

    assert "embedding" not in exploitation
    assert exploitation["title"] == article.title
    assert exploitation["keywords"] == article.keywords
    assert exploitation["publishable"] is True
    assert exploitation["embedding_dimension"] == settings.EMBEDDING_DIMENSION

    # And the whole chain is walkable from the article id alone.
    trace = lake.trace(article.id)

    assert [entry["layer"] for entry in trace["manifest"]] == [
        "raw",
        "processed",
        "exploitation",
    ]
    assert all(entry["run_id"] == run.run_id for entry in trace["manifest"])
