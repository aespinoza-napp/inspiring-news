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


def test_low_constructiveness_fails():

    validator = PositiveImpactValidator()

    quality = create_quality(
        constructiveness=0.10,
    )

    result = validator.validate(
        create_sentiment(),
        quality,
    )

    assert not result.passed


def test_low_inspirational_score_fails():

    validator = PositiveImpactValidator()

    quality = create_quality(
        inspirational_score=0.10,
    )

    result = validator.validate(
        create_sentiment(),
        quality,
    )

    assert not result.passed


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
