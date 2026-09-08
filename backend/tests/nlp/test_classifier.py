from src.config.topics import TOPICS
from src.processors.nlp.classifier import TopicClassifier


def test_topic_classifier():

    classifier = TopicClassifier()

    text = """
    OpenAI announced a new artificial intelligence
    model that improves programming and reasoning.
    """

    predictions = classifier.process(text)

    assert isinstance(predictions, list)

    assert len(predictions) > 0

    # This previously asserted an "artificial_intelligence" topic, which
    # is not one of the configured TOPICS at all - the assertion could
    # never pass. Assert the real contract instead: every prediction is a
    # configured topic, they come back ranked, and the probabilities are
    # a distribution.
    assert all(prediction.topic in TOPICS for prediction in predictions)

    assert predictions[0].topic == "technology"

    confidences = [prediction.confidence for prediction in predictions]
    assert confidences == sorted(confidences, reverse=True)

    assert all(
        0.0 <= prediction.confidence <= 1.0
        and 0.0 <= prediction.probability <= 1.0
        for prediction in predictions
    )

    # Tolerance, not 1e-6: TopicClassifier rounds each probability to 4
    # decimals, so across ~20 topics the rounding error alone reaches
    # ~1e-4 and the sum lands on e.g. 1.0001.
    assert abs(sum(p.probability for p in predictions) - 1.0) < 1e-3


def test_off_topic_text_returns_no_predictions():

    classifier = TopicClassifier(threshold=0.99)

    assert classifier.process("asdf qwerty zxcv") == []
