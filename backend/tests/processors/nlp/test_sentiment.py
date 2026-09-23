"""
SentimentAnalyzer is now an Adapter over InferenceClient - the real
model (and its @user/http normalization) moved to
inference/tests/test_sentiment.py. This tests the adapter: it builds a
SentimentResult from whatever the client returns, and propagates
failure rather than degrading (see sentiment.py's docstring for why:
PositiveImpactScorer reads this as a core admission signal).
"""

import pytest

from src.processors.nlp.sentiment import SentimentAnalyzer
from src.services.inference_client import InferenceUnavailable


class _StubClient:

    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def sentiment(self, text):
        self.calls.append(text)
        if self.error:
            raise self.error
        return self.result


RESULT = {
    "label": "positive",
    "positive": 0.70,
    "neutral": 0.25,
    "negative": 0.05,
    "polarity": 0.65,
    "subjectivity": 0.3,
    "confidence": 0.70,
    "emotional_intensity": 0.65,
}


def test_process_builds_a_sentiment_result_from_the_client_response():

    analyzer = SentimentAnalyzer(client=_StubClient(result=RESULT))

    result = analyzer.process("Scientists announced a breakthrough treatment.")

    assert result.label == "positive"
    assert result.positive == 0.70
    assert result.negative == 0.05


def test_accepts_and_ignores_a_legacy_cfg_positional_argument():
    """
    Every call site still passes SentimentAnalyzer(cfg) or
    SentimentAnalyzer(settings) - accepted so none of them needed to
    change, even though cfg no longer selects a model to load locally.
    """

    class FakeSettings:
        SENTIMENT_MODEL = "irrelevant-now"

    analyzer = SentimentAnalyzer(FakeSettings(), client=_StubClient(result=RESULT))

    assert analyzer.process("text").label == "positive"


def test_raises_when_the_client_fails_rather_than_degrading():

    analyzer = SentimentAnalyzer(client=_StubClient(error=InferenceUnavailable("down")))

    with pytest.raises(InferenceUnavailable):
        analyzer.process("text")
