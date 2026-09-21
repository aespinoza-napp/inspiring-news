from __future__ import annotations

import re
from typing import List

import numpy as np

from src.config.settings import settings
from src.config.topics import TOPICS
from src.models.nlp.topic_prediction import TopicKeyword, TopicPrediction
from src.services.embeddings.service import EmbeddingService

from .base import BaseProcessor


class TopicClassifier(BaseProcessor):

    _topic_embeddings = None

    # topic_id -> [(keyword, vector), ...]
    _keyword_embeddings = None

    def __init__(
        self,
        threshold: float | None = None,
        embedding_service: EmbeddingService | None = None,
    ):

        self.embedding_service = embedding_service or EmbeddingService()

        # Instance default, overridable per call - see process(). The
        # classifier is a long-lived singleton shared by every request,
        # so a per-run threshold cannot live on the instance.
        self.threshold = (
            threshold
            if threshold is not None
            else settings.TOPIC_CLASSIFIER_THRESHOLD
        )

        if TopicClassifier._topic_embeddings is None:

            # Built aside and assigned at the end. Assigning the empty dict
            # first left the class holding a half-filled cache whenever the
            # inference service failed partway, and every later instance
            # then skipped this block and classified against fewer topics.
            topic_embeddings = {}

            for topic_id, topic in TOPICS.items():

                topic_text = f"""
                {topic.name}

                {topic.description}

                Keywords:
                {", ".join(topic.keywords)}
                """

                topic_embeddings[topic_id] = (
                    self.embedding_service.encode(topic_text)
                )

            TopicClassifier._topic_embeddings = topic_embeddings

        if TopicClassifier._keyword_embeddings is None:

            # One batched call for every keyword of every topic, once per
            # process - scoring an article against them afterwards is
            # arithmetic only.
            terms = [
                (topic_id, keyword)
                for topic_id, topic in TOPICS.items()
                for keyword in topic.keywords
            ]

            vectors = self.embedding_service.encode_many(
                [keyword for _, keyword in terms]
            )

            keyword_embeddings: dict = {topic_id: [] for topic_id in TOPICS}

            for (topic_id, keyword), vector in zip(terms, vectors):
                keyword_embeddings[topic_id].append((keyword, vector))

            TopicClassifier._keyword_embeddings = keyword_embeddings

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
                keywords=self._score_keywords(
                    topic_id, article_embedding, text
                ),
            )

            for (topic_id, confidence), probability
            in zip(similarities, probabilities)

        ]

    def _score_keywords(
        self,
        topic_id: str,
        article_embedding,
        text: str,
    ) -> List[TopicKeyword]:
        """
        The topic's own keywords, ranked by how close each is to this
        article. Similarity rather than literal matching because the
        keyword lists are English and 7 of the 12 sources publish in
        Spanish; `mentions` adds the literal count for the cases where the
        word really is in the text.
        """

        scored = [
            TopicKeyword(
                keyword=keyword,
                score=round(float(np.dot(article_embedding, vector)), 4),
                mentions=len(
                    re.findall(
                        rf"(?<!\w){re.escape(keyword)}(?!\w)",
                        text,
                        flags=re.IGNORECASE,
                    )
                ),
            )
            for keyword, vector in self._keyword_embeddings[topic_id]
        ]

        scored.sort(key=lambda item: item.score, reverse=True)

        return scored
