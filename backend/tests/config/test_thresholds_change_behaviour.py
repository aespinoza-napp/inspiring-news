"""
Each threshold must actually reach the component it names.

The tests above prove the values resolve correctly; these prove they are
*used*. That gap is exactly where the old design failed: the values were
present in settings and looked wired, but every component had frozen them
into a class attribute at import time, so nothing a caller passed could
ever take effect.
"""

from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim
from src.models.nlp.quality import Quality
from src.models.nlp.sentiment_result import SentimentResult
from src.models.nlp.topic_prediction import TopicPrediction
from src.models.scraper.extraction import ExtractionResult
from src.services.fact_checker.claim_selector import ClaimSelector
from src.services.fact_checker.validators.positive_impact_validator import (
    PositiveImpactValidator,
)
from src.services.fact_checker.validators.topic_validator import TopicValidator
from src.services.scraper.extraction_validator import ExtractionValidator

from tests.factories import create_article, create_claim
from tests.fact_checker.fakes import FakeEmbeddingService


# ----------------------------------------------------------------------
# Admission filter
# ----------------------------------------------------------------------


def make_quality(**kwargs) -> Quality:

    values = dict(
        readability=0.8,
        objectivity=0.8,
        constructiveness=0.5,
        inspirational_score=0.5,
        hopefulness=0.5,
        societal_impact=0.8,
        novelty=0.5,
    )
    values.update(kwargs)

    return Quality(**values)


def make_sentiment(**kwargs) -> SentimentResult:

    values = dict(
        label="positive",
        positive=0.7,
        neutral=0.2,
        negative=0.1,
        polarity=0.6,
        subjectivity=0.2,
        confidence=0.95,
        emotional_intensity=0.4,
    )
    values.update(kwargs)

    return SentimentResult(**values)


def test_positive_impact_min_score_decides_admission():

    validator = PositiveImpactValidator()

    sentiment, quality = make_sentiment(), make_quality()

    # The same article, judged against a lenient and a strict bar.
    lenient = validator.validate(
        sentiment, quality, PipelineThresholds(positive_impact_min_score=0.10)
    )
    strict = validator.validate(
        sentiment, quality, PipelineThresholds(positive_impact_min_score=0.99)
    )

    assert lenient.passed is True
    assert strict.passed is False

    # The score itself is a property of the article, not of the bar.
    assert lenient.score == strict.score


def test_positive_impact_falls_back_to_the_default_when_not_given():

    validator = PositiveImpactValidator()

    explicit = validator.validate(
        make_sentiment(), make_quality(), PipelineThresholds()
    )
    implicit = validator.validate(make_sentiment(), make_quality())

    assert explicit.passed == implicit.passed
    assert explicit.score == implicit.score


def test_topic_min_confidence_decides_whether_an_article_is_on_topic():

    validator = TopicValidator()

    article = create_article(
        topics=[TopicPrediction(topic="climate", confidence=0.40, probability=0.4)]
    )

    assert validator.validate(article, PipelineThresholds(topic_min_confidence=0.30))
    assert not validator.validate(
        article, PipelineThresholds(topic_min_confidence=0.50)
    )


def test_topic_validator_still_rejects_an_article_with_no_topics_at_all():
    """
    A threshold of 0.0 lowers the bar; it does not invent a topic.
    """

    validator = TopicValidator()

    article = create_article(topics=[])

    assert not validator.validate(article, PipelineThresholds(topic_min_confidence=0.0))


# ----------------------------------------------------------------------
# Extraction
# ----------------------------------------------------------------------


def test_min_body_length_decides_whether_an_extraction_is_accepted():

    article = ExtractionResult(source_id="web", body="x" * 300)

    assert ExtractionValidator.is_valid(article, PipelineThresholds(min_body_length=100))
    assert not ExtractionValidator.is_valid(
        article, PipelineThresholds(min_body_length=500)
    )


def test_min_body_length_defaults_when_no_thresholds_are_passed():

    short = ExtractionResult(source_id="web", body="x" * 10)
    long = ExtractionResult(source_id="web", body="x" * 5000)

    assert not ExtractionValidator.is_valid(short)
    assert ExtractionValidator.is_valid(long)


# ----------------------------------------------------------------------
# Claim selection
# ----------------------------------------------------------------------


def make_claims(count: int) -> list[Claim]:

    return [
        create_claim(text=f"Distinct claim number {index}.", confidence=0.9 - index * 0.01)
        for index in range(count)
    ]


def test_max_claims_per_article_caps_the_selection():

    selector = ClaimSelector(embeddings=FakeEmbeddingService())

    claims = make_claims(5)

    assert (
        len(selector.select(claims, PipelineThresholds(max_claims_per_article=2)).selected)
        == 2
    )
    assert (
        len(selector.select(claims, PipelineThresholds(max_claims_per_article=4)).selected)
        == 4
    )


def test_claims_cut_by_the_cap_are_reported_as_rejected_not_dropped():

    selector = ClaimSelector(embeddings=FakeEmbeddingService())

    result = selector.select(
        make_claims(5), PipelineThresholds(max_claims_per_article=2)
    )

    assert len(result.selected) == 2
    assert len(result.rejected) == 3
    assert all(
        rejected.reason == "exceeds_max_claims_cap" for rejected in result.rejected
    )


def test_claim_dedup_threshold_controls_how_aggressively_claims_collapse():
    """
    FakeEmbeddingService scores identical text 1.0 and different text
    lower, so a threshold above that lower score keeps both claims and
    one at/below it collapses them.
    """

    selector = ClaimSelector(embeddings=FakeEmbeddingService())

    claims = [
        create_claim(text="NASA discovered water on Mars.", confidence=0.9),
        create_claim(text="NASA discovered water on Mars.", confidence=0.8),
    ]

    collapsed = selector.select(claims, PipelineThresholds(claim_dedup_threshold=0.99))

    assert len(collapsed.selected) == 1
    assert collapsed.rejected[0].reason == "semantic_duplicate"


def test_claim_selection_falls_back_to_defaults_when_not_given():

    selector = ClaimSelector(embeddings=FakeEmbeddingService())

    claims = make_claims(20)

    assert (
        len(selector.select(claims).selected)
        == PipelineThresholds().max_claims_per_article
    )
