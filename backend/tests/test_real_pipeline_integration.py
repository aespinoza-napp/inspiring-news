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
from src.models.core.news import News
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
    assert len(selection.selected) <= ClaimSelector.MAX_CLAIMS

    # Every extracted claim's entities were themselves drawn from the
    # same GLiNER pass - sanity-check the shape survives the round trip.
    for claim in selection.selected:
        assert isinstance(claim.text, str) and claim.text.strip()
        assert 0.0 <= claim.confidence <= 1.0
