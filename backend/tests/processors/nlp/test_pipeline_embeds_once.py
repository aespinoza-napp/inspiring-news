"""
The enrichment pipeline embeds an article once.

It used to embed `article.content` for storage and then hand the same
text to the topic classifier, which embedded it again: the whole
article, the most expensive embedding of an analysis (3.0 s for a
5,700-character article on the dev laptop's CPU, 2026-10-16), twice,
for an identical vector. Runs without inference/: every processor is a
stand-in, so what is tested is the wiring.
"""

import numpy as np

from src.models.core.news import News
from src.models.nlp.quality import Quality
from src.models.nlp.sentiment_result import SentimentResult
from src.workflows.enrichment import NewsEnrichmentPipeline


class _Returns:

    def __init__(self, result):
        self.result = result

    def process(self, *args, **kwargs):
        return self.result


class _RecordingClassifier:

    def __init__(self):
        self.embeddings = []

    def process(self, text, threshold=None, embedding=None):
        self.embeddings.append(embedding)
        return []


class _CountingEmbedding:

    class service:
        model_name = "bge-m3"

    def __init__(self):
        self.texts = []

    def process(self, text):
        self.texts.append(text)
        return np.array([0.6, 0.8])


def test_the_article_is_embedded_once_and_the_classifier_reuses_the_vector():

    pipeline = NewsEnrichmentPipeline.__new__(NewsEnrichmentPipeline)
    pipeline.keywords = _Returns([])
    pipeline.entities = _Returns({})
    pipeline.claims = _Returns([])
    pipeline.topics = _RecordingClassifier()
    pipeline.sentiment = _Returns(SentimentResult(
        label="neutral", positive=0.2, neutral=0.7, negative=0.1,
        polarity=0.1, subjectivity=0.3, confidence=0.9,
        emotional_intensity=0.2,
    ))
    pipeline.quality = _Returns(Quality(
        readability=0.8, objectivity=0.8, constructiveness=0.8,
        inspirational_score=0.8, hopefulness=0.8, societal_impact=0.8,
        novelty=0.5,
    ))
    pipeline.embedding = _CountingEmbedding()

    news = News(
        source_id="bbc",
        url="https://bbc.com/drones",
        title="Drones help a flood response",
        language="en",
        content="A drone programme trained thirty experts before the floods.",
    )

    enriched = pipeline.process(news)

    assert pipeline.embedding.texts == [news.content]
    assert len(pipeline.topics.embeddings) == 1
    assert list(pipeline.topics.embeddings[0]) == [0.6, 0.8]
    assert enriched.embedding == [0.6, 0.8]
