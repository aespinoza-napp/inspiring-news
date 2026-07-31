from __future__ import annotations

import re

from src.models.core.claim import Claim
from src.processors.nlp.entities import EntityExtractor

from .base import BaseProcessor


class ClaimExtractor(BaseProcessor):

    REPORTING_VERBS = {
        "announce",
        "announced",
        "say",
        "said",
        "report",
        "reported",
        "confirm",
        "confirmed",
        "discover",
        "discovered",
        "find",
        "found",
        "reveal",
        "revealed",
        "publish",
        "published",
        "launch",
        "launched",
        "approve",
        "approved",
        "win",
        "won",
        "identify",
        "identified",
        "detect",
        "detected",
        "increase",
        "increased",
        "reduce",
        "reduced",
        "improve",
        "improved",
        "show",
        "showed",
        "demonstrate",
        "demonstrated",
        "indicate",
        "indicated",
        "estimate",
        "estimated",
    }

    DATE_PATTERN = re.compile(
        r"\b("
        r"\d{4}"
        r"|january|february|march|april|may|june|july|"
        r"august|september|october|november|december|"
        r"today|yesterday|tomorrow"
        r")\b",
        re.IGNORECASE,
    )

    NUMBER_PATTERN = re.compile(r"\d+(?:[.,]\d+)?")

    MEASUREMENT_PATTERN = re.compile(
        r"\b("
        r"%|percent|km|m|cm|kg|g|tons?|"
        r"million|billion|euros?|dollars?|people"
        r")\b",
        re.IGNORECASE,
    )

    QUOTE_PATTERN = re.compile(r"[\"“”']")

    def __init__(self):

        self.entity_extractor = EntityExtractor()

    ##########################################################

    def process(
        self,
        text: str,
    ) -> list[Claim]:

        claims = []

        for sentence in self._split_sentences(text):

            entities = self.entity_extractor.process(sentence)

            confidence = self._score(
                sentence,
                entities,
            )

            if confidence < 0.50:
                continue

            claims.append(
                Claim(
                    text=sentence,
                    entities=entities,
                    confidence=round(confidence, 2),
                )
            )

        return claims

    ##########################################################

    def _split_sentences(
        self,
        text: str,
    ) -> list[str]:

        return [
            s.strip()
            for s in re.split(
                r"(?<=[.!?])\s+",
                text,
            )
            if s.strip()
        ]

    ##########################################################

    def _score(
        self,
        sentence: str,
        entities,
    ) -> float:

        score = 0.0

        sentence_lower = sentence.lower()

        ##################################################
        # Named entities
        ##################################################

        if entities:
            score += 0.25

        ##################################################
        # Numbers
        ##################################################

        if self.NUMBER_PATTERN.search(sentence):
            score += 0.20

        ##################################################
        # Dates
        ##################################################

        if self.DATE_PATTERN.search(sentence):
            score += 0.15

        ##################################################
        # Measurements
        ##################################################

        if self.MEASUREMENT_PATTERN.search(sentence):
            score += 0.10

        ##################################################
        # Reporting verbs
        ##################################################

        if any(
            verb in sentence_lower
            for verb in self.REPORTING_VERBS
        ):
            score += 0.20

        ##################################################
        # Quotes
        ##################################################

        if self.QUOTE_PATTERN.search(sentence):
            score += 0.05

        ##################################################
        # Long informative sentences
        ##################################################

        if len(sentence.split()) >= 8:
            score += 0.05

        ##################################################
        # Upper bound
        ##################################################

        return min(score, 1.0)