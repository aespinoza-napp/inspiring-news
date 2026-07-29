from __future__ import annotations

import re

import textstat

from .base import BaseProcessor


SPECULATIVE = {
    "may",
    "might",
    "could",
    "perhaps",
    "possibly",
    "likely",
    "apparently",
    "allegedly",
}

EMOTIONAL = {
    "amazing",
    "incredible",
    "shocking",
    "terrible",
    "catastrophic",
    "unbelievable",
}

FIRST_PERSON = {
    "i",
    "we",
    "our",
    "my",
}

CONSTRUCTIVE = {
    "developed",
    "created",
    "improved",
    "innovation",
    "initiative",
    "project",
    "solution",
    "research",
    "discover",
    "restored",
    "reduced",
    "increase",
    "collaboration",
    "technology",
    "treatment",
    "vaccine",
}

NEGATIVE = {
    "war",
    "attack",
    "conflict",
    "crisis",
    "collapse",
    "disaster",
    "problem",
}

HOPE = {
    "recover",
    "recovery",
    "improve",
    "growth",
    "restore",
    "save",
    "protect",
    "conservation",
    "breakthrough",
    "success",
    "cure",
    "treatment",
    "vaccine",
}

HUMAN = {
    "student",
    "teacher",
    "doctor",
    "scientist",
    "researcher",
    "volunteer",
    "community",
    "family",
}

GLOBAL = {
    "world",
    "global",
    "international",
    "millions",
    "thousands",
    "un",
    "who",
    "eu",
    "nasa",
}


class QualityAnalyzer(BaseProcessor):

    WORD = re.compile(r"\b[\w'-]+\b")

    def process(
        self,
        text: str,
        *,
        sentiment=None,
        entities=None,
        novelty=None,
    ):

        return {

            "readability":
                self.readability(text),

            "objectivity":
                self.objectivity(
                    text,
                    entities,
                ),

            "constructiveness":
                self.constructiveness(text),

            "hopefulness":
                self.hopefulness(text),

            "societal_impact":
                self.societal_impact(
                    text,
                    entities,
                ),

            "inspirational_score":
                self.inspiration(
                    text,
                    sentiment,
                ),

            "novelty":
                novelty if novelty is not None else 0.5,
        }

    #######################################################

    def _words(self, text):

        return [
            w.lower()
            for w in self.WORD.findall(text)
        ]

    #######################################################

    def readability(self, text):

        score = textstat.flesch_reading_ease(text)

        return round(

            max(
                0,
                min(score / 100, 1),
            ),

            4,
        )

    #######################################################

    def constructiveness(self, text):

        words = self._words(text)

        positive = sum(
            w in CONSTRUCTIVE
            for w in words
        )

        negative = sum(
            w in NEGATIVE
            for w in words
        )

        return round(

            positive /
            (positive + negative + 1),

            4,
        )

    #######################################################

    def hopefulness(self, text):

        words = self._words(text)

        count = sum(
            w in HOPE
            for w in words
        )

        return round(

            min(
                count / 10,
                1,
            ),

            4,
        )

    #######################################################

    def societal_impact(
        self,
        text,
        entities,
    ):

        words = self._words(text)

        score = 0

        score += sum(
            w in GLOBAL
            for w in words
        )

        if entities:

            score += min(
                len(entities) / 10,
                1,
            )

        return round(

            min(
                score / 5,
                1,
            ),

            4,
        )

    #######################################################

    def objectivity(
        self,
        text,
        entities,
    ):

        words = self._words(text)

        speculative = sum(
            w in SPECULATIVE
            for w in words
        )

        emotional = sum(
            w in EMOTIONAL
            for w in words
        )

        first_person = sum(
            w in FIRST_PERSON
            for w in words
        )

        factual = 0

        if entities:

            factual += min(
                len(entities),
                15,
            )

        factual += len(
            re.findall(r"\d+", text)
        )

        score = (

            factual

            - speculative

            - emotional

            - first_person

        )

        return round(

            max(
                0,
                min(
                    score / 15,
                    1,
                ),
            ),

            4,
        )

    #######################################################

    def inspiration(
        self,
        text,
        sentiment,
    ):

        words = self._words(text)

        human = sum(
            w in HUMAN
            for w in words
        )

        hope = self.hopefulness(text)

        constructive = self.constructiveness(text)

        positivity = 0.5

        if sentiment:

            positivity = sentiment.positive

        score = (

            positivity * 0.35 +

            constructive * 0.30 +

            hope * 0.20 +

            min(
                human / 5,
                1,
            ) * 0.15

        )

        return round(
            min(score, 1),
            4,
        )