from __future__ import annotations

import re

from src.config.settings import settings
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

    # "%" is matched outside the \b(...)\b group: it is not a word
    # character, so inside that group it could never match at all
    # ("35%." has no word boundary after the "%"). That silently cost
    # every percentage sentence 0.10 of its score - enough to push
    # "The treatment increased survival by 35%." below the 0.50 claim
    # threshold and drop the claim entirely.
    MEASUREMENT_PATTERN = re.compile(
        r"%|\b("
        r"percent|km|m|cm|kg|g|tons?|"
        r"million|billion|euros?|dollars?|people"
        r")\b",
        re.IGNORECASE,
    )

    QUOTE_PATTERN = re.compile(r"[\"“”']")

    def __init__(self, min_confidence: float | None = None):

        self.entity_extractor = EntityExtractor()

        # Instance default, overridable per call - see process().
        self.min_confidence = (
            min_confidence
            if min_confidence is not None
            else settings.CLAIM_MIN_CONFIDENCE
        )

    ##########################################################

    def process(
        self,
        text: str,
        min_confidence: float | None = None,
        entity_threshold: float | None = None,
    ) -> list[Claim]:

        minimum = (
            min_confidence
            if min_confidence is not None
            else self.min_confidence
        )

        claims = []

        for sentence in self._split_sentences(text):

            entities = self.entity_extractor.process(sentence, entity_threshold)

            confidence = self._score(
                sentence,
                entities,
            )

            if confidence < minimum:
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
