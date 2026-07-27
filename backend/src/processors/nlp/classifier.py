from __future__ import annotations

from typing import List

import numpy as np

from src.config.topics import TOPICS
from src.services.embeddings.service import EmbeddingService

from .base import BaseProcessor


class TopicClassifier(BaseProcessor):

    _topic_embeddings = None

    def __init__(
        self,
        threshold: float = 0.45,
    ):

        self.embedding_service = EmbeddingService()

        self.threshold = threshold

        if TopicClassifier._topic_embeddings is None:

            TopicClassifier._topic_embeddings = {

                topic_id: self.embedding_service.encode(
                    topic.description
                )

                for topic_id, topic in TOPICS.items()

            }

    def process(self, text: str) -> List[str]:

        article_embedding = self.embedding_service.encode(
            text
        )

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

        similarities.sort(
            key=lambda item: item[1],
            reverse=True,
        )

        return [
            topic
            for topic, _
            in similarities
        ]