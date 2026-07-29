from __future__ import annotations

import re

from src.models.claim import Claim
from src.processors.nlp.entities import EntityExtractor

from .base import BaseProcessor


class ClaimExtractor(BaseProcessor):

    CLAIM_VERBS = {
        "is",
        "are",
        "was",
        "were",
        "has",
        "have",
        "had",
        "announced",
        "said",
        "reported",
        "confirmed",
        "developed",
        "created",
        "discovered",
        "found",
        "revealed",
        "published",
        "launched",
        "approved",
        "won",
        "became",
        "identified",
        "detected",
        "improved",
        "reduced",
        "increased",
    }

    def __init__(self):

        self.entity_extractor = EntityExtractor()

    def process(
        self,
        text: str,
    ) -> list[Claim]:

        claims = []

        sentences = self._split_sentences(text)

        for sentence in sentences:

            if not self._is_claim(sentence):

                continue

            entities = self.entity_extractor.process(sentence)

            confidence = self._confidence(
                sentence,
                entities,
            )

            claims.append(

                Claim(

                    text=sentence,

                    entities=entities,

                    confidence=confidence,

                )

            )

        return claims

    ##########################################################

    def _split_sentences(
        self,
        text: str,
    ) -> list[str]:

        return [

            sentence.strip()

            for sentence in re.split(
                r"(?<=[.!?])\s+",
                text,
            )

            if sentence.strip()

        ]

    ##########################################################

    def _is_claim(
        self,
        sentence: str,
    ) -> bool:

        sentence_lower = sentence.lower()

        if any(
            verb in sentence_lower
            for verb in self.CLAIM_VERBS
        ):
            return True

        if re.search(r"\d", sentence):
            return True

        return False

    ##########################################################

    def _confidence(
        self,
        sentence: str,
        entities: list[str],
    ) -> float:

        score = 0.4

        if entities:
            score += 0.2

        if re.search(r"\d", sentence):
            score += 0.2

        if '"' in sentence:
            score += 0.1

        if len(sentence.split()) > 8:
            score += 0.1

        return round(
            min(score, 1.0),
            2,
        )