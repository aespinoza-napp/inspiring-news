from src.processors.nlp.classifier import TopicClassifier


def test_topic_classifier():

    classifier = TopicClassifier()

    text = """
    OpenAI announced a new artificial intelligence
    model that improves programming and reasoning.
    """

    predictions = classifier.process(text)

    print(predictions)

    assert isinstance(predictions, list)

    assert len(predictions) > 0

    assert predictions[0].topic == "artificial_intelligence"

    assert 0.0 <= predictions[0].confidence <= 1.0

    assert 0.0 <= predictions[0].probability <= 1.0

    assert abs(
        sum(p.probability for p in predictions) - 1.0
    ) < 1e-6

test_topic_classifier()