from unittest.mock import Mock

from src.config.thresholds import PipelineThresholds
from src.services.enrichment_service import EnrichmentService

from tests.factories import create_article, create_claim

TEXT = "NASA discovered water on Mars. Scientists confirmed the finding."


def make_service(article=None):

    pipeline = Mock()
    pipeline.process.return_value = article if article is not None else create_article()

    return EnrichmentService(pipeline=pipeline)


# ----------------------------------------------------------------------
# It reuses the real pipeline, unchanged
# ----------------------------------------------------------------------


def test_the_text_is_wrapped_in_a_news_object_for_the_pipeline():

    service = make_service()

    service.enrich(TEXT, title="A title")

    news = service.pipeline.process.call_args[0][0]

    assert news.content == TEXT
    assert news.title == "A title"


def test_manual_text_is_marked_as_not_coming_from_a_configured_source():
    """
    It was never fetched from anywhere. If such a record ever did reach
    storage it must not look like a scraped article.
    """

    service = make_service()

    service.enrich(TEXT)

    news = service.pipeline.process.call_args[0][0]

    assert news.source_id == "manual"
    assert news.url == "about:blank"


def test_a_supplied_url_is_kept():

    service = make_service()

    service.enrich(TEXT, url="https://example.com/a")

    assert service.pipeline.process.call_args[0][0].url == "https://example.com/a"


def test_thresholds_reach_the_pipeline():

    service = make_service()

    service.enrich(TEXT, thresholds=PipelineThresholds(topic_classifier_threshold=0.9))

    thresholds = service.pipeline.process.call_args[0][1]

    assert thresholds.topic_classifier_threshold == 0.9


def test_defaults_are_used_when_no_thresholds_are_given():

    service = make_service()

    service.enrich(TEXT)

    assert service.pipeline.process.call_args[0][1] == PipelineThresholds()


# ----------------------------------------------------------------------
# Shape
# ----------------------------------------------------------------------


def test_every_enrichment_field_is_reported():

    article = create_article(
        keywords=["mars", "water"],
        entities={"organization": ["NASA"]},
        claims=[create_claim(text="NASA discovered water.", confidence=0.8)],
    )

    result = make_service(article=article).enrich(TEXT)

    assert result["keywords"] == ["mars", "water"]
    assert result["entities"] == {"organization": ["NASA"]}
    assert result["topics"][0]["topic"] == "environment"
    assert result["claims"] == [
        {
            "text": "NASA discovered water.",
            "confidence": 0.8,
            "entities": {"ORG": ["NASA"]},
        }
    ]
    assert result["sentiment"]["label"] == "neutral"
    assert result["sentiment"]["emotionalIntensity"] == 0.2
    assert result["quality"]["constructiveness"] == 0.8


def test_the_embedding_is_summarised_not_inlined():
    """
    1024 floats are useless to a UI and larger than everything else in
    the response combined - report the shape and a preview instead.
    """

    result = make_service().enrich(TEXT)

    assert result["embedding"]["model"] == "bge-m3"
    assert result["embedding"]["dimension"] == 1024
    assert len(result["embedding"]["preview"]) == 8


def test_missing_optional_fields_become_empty_collections():

    article = create_article(keywords=None, topics=None, claims=None, entities={})

    result = make_service(article=article).enrich(TEXT)

    assert result["keywords"] == []
    assert result["topics"] == []
    assert result["claims"] == []
    assert result["entities"] == {}


def test_the_effective_thresholds_are_echoed_back():

    result = make_service().enrich(
        TEXT,
        thresholds=PipelineThresholds(claim_min_confidence=0.7),
    )

    assert result["thresholds"]["claim_min_confidence"] == 0.7


# ----------------------------------------------------------------------
# Side effects
# ----------------------------------------------------------------------


def test_enrichment_writes_nothing_anywhere():
    """
    An inspection tool, not an ingestion path: the service holds no lake
    and no repository, so there is nothing for it to write with. Pinned
    because "just also store it" is the tempting next change, and it
    would fill the raw layer with text nobody ever fetched.
    """

    service = make_service()

    service.enrich(TEXT)

    assert not hasattr(service, "lake")
    assert not hasattr(service, "repository")


def test_phases_are_reported():

    events = []

    make_service().enrich(TEXT, on_phase=lambda phase, data: events.append(phase))

    assert events == ["enriching", "enriched"]
