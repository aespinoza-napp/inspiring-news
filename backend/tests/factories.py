from datetime import datetime

from src.models.enriched_article import EnrichedArticle
from src.models.quality import Quality
from src.models.sentiment_result import SentimentResult
from src.models.topic_prediction import TopicPrediction

def create_article(**kwargs) -> EnrichedArticle:

    article = EnrichedArticle(
        id="11111111-1111-1111-1111-111111111111",
        source_id="bbc",
        url="https://bbc.com/test",
        title="Test article",
        body="This is a test article.",
        language="en",
        published_at=datetime.now(),

        keywords=["test"],
        entities={},

        topics=[TopicPrediction(topic="environment", confidence=0.71, probability=0.71)],
        claims=[],

        sentiment=SentimentResult(
            label="neutral",
            positive=0.2,
            neutral=0.7,
            negative=0.1,
            polarity=0.1,
            subjectivity=0.3,
            confidence=0.95,
            emotional_intensity=0.2,
        ),

        quality=Quality(
            readability=0.8,
            objectivity=0.8,
            constructiveness=0.8,
            inspirational_score=0.8,
            hopefulness=0.8,
            societal_impact=0.8,
            novelty=0.5,
        ),

        embedding=[0.1] * 1024,
        embedding_model="bge-m3",
        embedding_dimension=1024,
    )

    article = article.model_copy(update=kwargs)

    return article