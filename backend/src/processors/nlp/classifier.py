from __future__ import annotations

from typing import List

import numpy as np

from src.config.settings import settings
from src.config.topics import TOPICS
from src.models.nlp.topic_prediction import TopicPrediction
from src.services.embeddings.service import EmbeddingService

from .base import BaseProcessor


class TopicClassifier(BaseProcessor):

    _topic_embeddings = None

    def __init__(
        self,
        threshold: float | None = None,
    ):

        self.embedding_service = EmbeddingService()

        # Instance default, overridable per call - see process(). The
        # classifier is a long-lived singleton shared by every request,
        # so a per-run threshold cannot live on the instance.
        self.threshold = (
            threshold
            if threshold is not None
            else settings.TOPIC_CLASSIFIER_THRESHOLD
        )

        if TopicClassifier._topic_embeddings is None:

            TopicClassifier._topic_embeddings = {}

            for topic_id, topic in TOPICS.items():

                topic_text = f"""
                {topic.name}

                {topic.description}

                Keywords:
                {", ".join(topic.keywords)}
                """

                TopicClassifier._topic_embeddings[topic_id] = (
                    self.embedding_service.encode(topic_text)
                )

    def process(
        self,
        text: str,
        threshold: float | None = None,
    ) -> List[TopicPrediction]:

        minimum = threshold if threshold is not None else self.threshold

        article_embedding = self.embedding_service.encode(text)

        similarities = []

        for topic_id, embedding in self._topic_embeddings.items():

            similarity = float(
                np.dot(
                    article_embedding,
                    embedding,
                )
            )

            if similarity >= minimum:

                similarities.append(
                    (
                        topic_id,
                        similarity,
                    )
                )

        if not similarities:
            return []

        similarities.sort(
            key=lambda x: x[1],
            reverse=True,
        )

        scores = np.array(
            [score for _, score in similarities]
        )

        # Softmax normalization
        exp = np.exp(scores - scores.max())

        probabilities = exp / exp.sum()

        return [

            TopicPrediction(
                # TOPICS[topic_id].name, not the bare topic_id: this used
                # to hand "fact_checking"/"mental_health" straight to the
                # caller instead of "Fact Checking"/"Mental Health" - the
                # display name every other Topic field (description,
                # keywords) already exists for, just never read here.
                topic=TOPICS[topic_id].name,
                confidence=round(confidence, 4),
                probability=round(float(probability), 4),
            )

            for (topic_id, confidence), probability
            in zip(similarities, probabilities)

        ]
