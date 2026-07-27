from src.processors.nlp.classifier import TopicClassifier


def test_topic_classifier():

    classifier = TopicClassifier()

    text = """
    OpenAI announced a new artificial intelligence
    model that improves programming and reasoning.
    """

    topics = classifier.process(text)

    print(topics)

    assert isinstance(topics, list)

    assert len(topics) > 0

    assert "Technology" in topics

test_topic_classifier()