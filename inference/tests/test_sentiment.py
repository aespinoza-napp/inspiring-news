"""
Moved from backend/tests/nlp/test_sentiment.py - this is where the real
sentiment model lives now.
"""

from src.sentiment import SentimentModel


def test_sentiment_analysis():

    model = SentimentModel()
    model.load()

    text = """
    Scientists developed a revolutionary treatment that
    significantly improves the survival rate of children
    with a rare disease.
    """

    result = model.analyze(text)

    assert result.label in ["positive", "neutral", "negative"]

    assert 0 <= result.positive <= 1
    assert 0 <= result.neutral <= 1
    assert 0 <= result.negative <= 1

    assert abs(result.positive + result.neutral + result.negative - 1) < 0.01

    assert -1 <= result.polarity <= 1
    assert 0 <= result.subjectivity <= 1
    assert 0 <= result.confidence <= 1
    assert 0 <= result.emotional_intensity <= 1


def test_sentiment_normalizes_mentions_and_urls():
    """
    @user/http normalization moved here with the model - it's this
    model's own preprocessing quirk (the underlying twitter-trained
    classifier expects @user/http tokens, not raw handles/URLs), not
    orchestration logic, so it stays with the model rather than being
    duplicated in backend's adapter.
    """

    model = SentimentModel()
    model.load()

    raw = "@someone check this out http://example.com/article"

    assert model._normalize(raw) == "@user check this out http"
