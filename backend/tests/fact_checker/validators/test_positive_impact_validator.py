from src.models.nlp.quality import Quality
from src.models.nlp.sentiment_result import SentimentResult

from src.services.fact_checker.validators.positive_impact_validator import PositiveImpactValidator


def create_quality(
    constructiveness=0.8,
    inspirational_score=0.8,
    hopefulness=0.7,
    objectivity=0.8,
    societal_impact=0.9,
    readability=0.8,
    novelty=0.5,
):

    return Quality(
        readability=readability,
        objectivity=objectivity,
        constructiveness=constructiveness,
        inspirational_score=inspirational_score,
        hopefulness=hopefulness,
        societal_impact=societal_impact,
        novelty=novelty,
    )


def create_sentiment(
    positive=0.70,
    neutral=0.20,
    negative=0.10,
    polarity=0.60,
    subjectivity=0.20,
    confidence=0.95,
    emotional_intensity=0.40,
    label="positive",
):

    return SentimentResult(
        label=label,
        positive=positive,
        neutral=neutral,
        negative=negative,
        polarity=polarity,
        subjectivity=subjectivity,
        confidence=confidence,
        emotional_intensity=emotional_intensity,
    )


def test_positive_article_passes():

    validator = PositiveImpactValidator()

    result = validator.validate(
        create_sentiment(),
        create_quality(),
    )

    assert result.passed


def test_high_negative_sentiment_fails():

    validator = PositiveImpactValidator()

    sentiment = create_sentiment(
        positive=0.05,
        neutral=0.10,
        negative=0.85,
        polarity=-0.80,
        label="negative",
    )

    result = validator.validate(
        sentiment,
        create_quality(),
    )

    assert not result.passed


def test_low_constructiveness_is_flagged_but_not_a_hard_fail():
    """
    Low constructiveness is a *reason*, not a hard fail - the hard-fail
    check for it is deliberately commented out in the validator (it
    rejected too many real articles). It still costs the article score,
    which is the assertion that actually pins the behaviour down; if the
    hard fail is ever restored, this test is the one to flip back.
    """

    validator = PositiveImpactValidator()

    baseline = validator.validate(create_sentiment(), create_quality())

    result = validator.validate(
        create_sentiment(),
        create_quality(constructiveness=0.10),
    )

    assert result.passed
    assert "Low constructiveness" in result.reasons
    assert result.score < baseline.score


def test_low_inspirational_score_is_flagged_but_not_a_hard_fail():

    validator = PositiveImpactValidator()

    baseline = validator.validate(create_sentiment(), create_quality())

    result = validator.validate(
        create_sentiment(),
        create_quality(inspirational_score=0.10),
    )

    assert result.passed
    assert "Low inspirational value" in result.reasons
    assert result.score < baseline.score


def test_low_objectivity_fails():

    validator = PositiveImpactValidator()

    quality = create_quality(
        objectivity=0.15,
    )

    result = validator.validate(
        create_sentiment(),
        quality,
    )

    assert not result.passed


def test_neutral_constructive_article_passes():

    validator = PositiveImpactValidator()

    sentiment = create_sentiment(
        label="neutral",
        positive=0.08,
        neutral=0.87,
        negative=0.05,
        polarity=0.02,
    )

    quality = create_quality(
        constructiveness=0.90,
        inspirational_score=0.75,
        societal_impact=1.0,
        hopefulness=0.65,
    )

    result = validator.validate(
        sentiment,
        quality,
    )

    assert result.passed


def test_score_is_normalised_to_the_zero_one_range():
    """
    The raw weighted sum runs to 3.50, so before normalisation the
    returned score was clamped to exactly 1.0 for almost every article -
    a constant, carrying no information, and making the MIN_SCORE gate
    unreachable. A perfect article should score 1.0; a merely good one
    should score below it.
    """

    validator = PositiveImpactValidator()

    perfect = validator.validate(
        create_sentiment(positive=1.0, neutral=0.0, negative=0.0, subjectivity=0.0),
        create_quality(
            constructiveness=1.0,
            inspirational_score=1.0,
            hopefulness=1.0,
            objectivity=1.0,
            societal_impact=1.0,
            readability=1.0,
        ),
    )

    good = validator.validate(create_sentiment(), create_quality())

    assert perfect.score == 1.0
    assert 0.0 < good.score < 1.0


def test_score_never_leaves_the_zero_one_range_for_a_bleak_article():

    validator = PositiveImpactValidator()

    result = validator.validate(
        create_sentiment(positive=0.0, neutral=0.0, negative=1.0, subjectivity=1.0),
        create_quality(
            constructiveness=0.0,
            inspirational_score=0.0,
            hopefulness=0.0,
            objectivity=0.0,
            societal_impact=0.0,
            readability=0.0,
        ),
    )

    assert result.score == 0.0
    assert not result.passed
