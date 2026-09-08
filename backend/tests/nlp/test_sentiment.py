from src.config.settings import Settings
from src.processors.nlp.sentiment import SentimentAnalyzer


def test_sentiment_analysis():

    analyzer = SentimentAnalyzer(
        Settings()
    )

    text = """
    Scientists developed a revolutionary treatment that
    significantly improves the survival rate of children
    with a rare disease.
    """

    result = analyzer.process(text)

    print(result)

    assert result.label in [
        "positive",
        "neutral",
        "negative",
    ]

    assert 0 <= result.positive <= 1

    assert 0 <= result.neutral <= 1

    assert 0 <= result.negative <= 1

    assert abs(
        result.positive
        + result.neutral
        + result.negative
        - 1
    ) < 0.01

    assert -1 <= result.polarity <= 1

    assert 0 <= result.subjectivity <= 1

    assert 0 <= result.confidence <= 1

    assert 0 <= result.emotional_intensity <= 1
