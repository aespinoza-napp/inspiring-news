from __future__ import annotations

from typing import List

import numpy as np

from src.config.topics import TOPICS
from src.models.nlp.topic_prediction import TopicPrediction
from src.services.embeddings.service import EmbeddingService

from .base import BaseProcessor


class TopicClassifier(BaseProcessor):

    _topic_embeddings = None

    def __init__(
        self,
        threshold: float = 0.35,
    ):

        self.embedding_service = EmbeddingService()

        self.threshold = threshold

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

    def process(self, text: str) -> List[TopicPrediction]:

        article_embedding = self.embedding_service.encode(text)

        similarities = []

        for topic_id, embedding in self._topic_embeddings.items():

            similarity = float(
                np.dot(
                    article_embedding,
                    embedding,
                )
            )

            if similarity >= self.threshold:

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
                topic=topic,
                confidence=round(confidence, 4),
                probability=round(float(probability), 4),
            )

            for (topic, confidence), probability
            in zip(similarities, probabilities)

        ]
