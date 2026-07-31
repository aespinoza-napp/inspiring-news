import pytest
from datetime import datetime

from src.models.core.claim import Claim
from src.models.core.enriched_article import EnrichedArticle
from src.models.nlp.quality import Quality
from src.models.nlp.sentiment_result import SentimentResult
from src.models.nlp.topic_prediction import TopicPrediction
from src.services.fact_checker.validators.topic_validator import TopicValidator


@pytest.fixture
def base_article():

    return EnrichedArticle(
        id="1",
        source_id="bbc",
        url="https://bbc.com/article",
        title="Test article",
        body="This is a test article.",
        language="en",
        published_at=datetime.now(),

        keywords=[],
        entities={},

        topics=[],
        claims=[],

        sentiment=SentimentResult(
            label="neutral",
            positive=0.2,
            neutral=0.7,
            negative=0.1,
            polarity=0.1,
            subjectivity=0.3,
            confidence=0.9,
            emotional_intensity=0.2,
        ),

        quality=Quality(
            readability=0.8,
            objectivity=0.8,
            constructiveness=0.8,
            inspirational_score=0.8,
            hopefulness=0.8,
            societal_impact=0.8,
            novelty=0.8,
        ),

        embedding=[0.1, 0.2, 0.3],
        embedding_model="bge-m3",
        embedding_dimension=3,
    )


def test_accepts_valid_topic(base_article):

    validator = TopicValidator()

    base_article.topics = [
        TopicPrediction(
            topic="science",
            confidence=0.82,
            probability=0.82,
        )
    ]

    assert validator.validate(base_article)


def test_rejects_empty_topics(base_article):

    validator = TopicValidator()

    base_article.topics = []

    assert not validator.validate(base_article)


def test_rejects_none_topics(base_article):

    validator = TopicValidator()

    base_article.topics = None

    assert not validator.validate(base_article)


def test_rejects_low_confidence(base_article):

    validator = TopicValidator()

    base_article.topics = [
        TopicPrediction(
            topic="science",
            confidence=0.20,
            probability=0.20,
        )
    ]

    assert not validator.validate(base_article)


def test_accepts_if_one_topic_is_above_threshold(base_article):

    validator = TopicValidator()

    base_article.topics = [
        TopicPrediction(topic="sports", confidence=0.10, probability=0.10),
        TopicPrediction(topic="environment", confidence=0.71, probability=0.71),
        TopicPrediction(topic="politics", confidence=0.18, probability=0.18),
    ]

    assert validator.validate(base_article)

