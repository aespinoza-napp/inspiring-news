from __future__ import annotations

import re
from typing import List

import numpy as np

from src.config.settings import settings
from src.config.editions import topics_of
from src.models.nlp.topic_prediction import TopicKeyword, TopicPrediction
from src.services.embeddings.service import EmbeddingService

from .base import BaseProcessor


class TopicClassifier(BaseProcessor):

    # edition -> topic_id -> vector
    _topic_embeddings = None

    # edition -> topic_id -> [(keyword, vector), ...]
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

        # The positive edition's labels are embedded at construction, as
        # they always were; the devastating edition's on its first run
        # (_labels), so a process that never runs one never pays for it.
        self._labels("positive")

    def _labels(self, edition: str) -> tuple[dict, dict]:
        """
        The edition's topic vectors and keyword vectors, embedded once per
        process per edition (src/config/editions.py).
        """

        topics = topics_of(edition)

        if edition not in (TopicClassifier._topic_embeddings or {}):

            # Built aside and assigned at the end. Assigning the empty dict
            # first left the class holding a half-filled cache whenever the
            # inference service failed partway, and every later instance
            # then skipped this block and classified against fewer topics.
            topic_embeddings = {}

            for topic_id, topic in topics.items():

                topic_text = f"""
                {topic.name}

                {topic.description}

                Keywords:
                {", ".join(topic.keywords)}
                """

                topic_embeddings[topic_id] = (
                    self.embedding_service.encode(topic_text)
                )

            # A new dict rather than a key added to the old one: another
            # request's thread may be reading it.
            TopicClassifier._topic_embeddings = {
                **(TopicClassifier._topic_embeddings or {}),
                edition: topic_embeddings,
            }

        if edition not in (TopicClassifier._keyword_embeddings or {}):

            # One batched call for every keyword of every topic, once per
            # process - scoring an article against them afterwards is
            # arithmetic only.
            terms = [
                (topic_id, keyword)
                for topic_id, topic in topics.items()
                for keyword in topic.keywords
            ]

            vectors = self.embedding_service.encode_many(
                [keyword for _, keyword in terms]
            )

            keyword_embeddings: dict = {topic_id: [] for topic_id in topics}

            for (topic_id, keyword), vector in zip(terms, vectors):
                keyword_embeddings[topic_id].append((keyword, vector))

            TopicClassifier._keyword_embeddings = {
                **(TopicClassifier._keyword_embeddings or {}),
                edition: keyword_embeddings,
            }

        return (
            TopicClassifier._topic_embeddings[edition],
            TopicClassifier._keyword_embeddings[edition],
        )

    def process(
        self,
        text: str,
        threshold: float | None = None,
        embedding=None,
        edition: str = "positive",
    ) -> List[TopicPrediction]:
        """
        `edition` chooses the labels (src/config/editions.py): TOPICS, or
        the Devastating edition's own.

        `embedding` is the text's vector when the caller already has it.
        The enrichment pipeline does - it embeds the article for storage -
        and encoding the same whole article again here doubled the most
        expensive embedding of an analysis: 3.0 s for a 5,700-character
        article on the laptop's CPU (2026-10-16), for an identical vector.
        """

        minimum = threshold if threshold is not None else self.threshold

        topics = topics_of(edition)
        topic_embeddings, keyword_embeddings = self._labels(edition)

        article_embedding = (
            embedding if embedding is not None
            else self.embedding_service.encode(text)
        )

        similarities = []

        for topic_id, topic_embedding in topic_embeddings.items():

            similarity = float(
                np.dot(
                    article_embedding,
                    topic_embedding,
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
                topic=topics[topic_id].name,
                confidence=round(confidence, 4),
                probability=round(float(probability), 4),
                keywords=self._score_keywords(
                    keyword_embeddings[topic_id], article_embedding, text
                ),
            )

            for (topic_id, confidence), probability
            in zip(similarities, probabilities)

        ]

    def _score_keywords(
        self,
        keywords: list,
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
            for keyword, vector in keywords
        ]

        scored.sort(key=lambda item: item.score, reverse=True)

        return scored
