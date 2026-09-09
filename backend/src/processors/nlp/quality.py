from __future__ import annotations

import re
import threading

import textstat

from src.config.lexicons import Lexicon, count_matches, lexicon_for

from .base import BaseProcessor


# textstat.set_lang() mutates module-global state, and this analyzer runs
# inside FastAPI's background threadpool - two concurrent analyses of
# articles in different languages would otherwise race, and one would be
# scored with the other's readability formula. The lock covers only the
# set-and-measure pair, which is microseconds.
_TEXTSTAT_LOCK = threading.Lock()


class QualityAnalyzer(BaseProcessor):

    WORD = re.compile(r"\b[\w'-]+\b")

    def process(
        self,
        text: str,
        *,
        sentiment=None,
        entities=None,
        novelty=None,
        language: str | None = None,
    ):
        """
        `language` picks the word lists and the readability formula. It
        defaults to English, so existing callers keep working - but
        passing it is what stops a Spanish article scoring 0 on every
        keyword metric and being rejected by the admission filter for it.
        """

        lexicon = lexicon_for(language)

        return {

            "readability":
                self.readability(text, lexicon),

            "objectivity":
                self.objectivity(
                    text,
                    entities,
                    lexicon,
                ),

            "constructiveness":
                self.constructiveness(text, lexicon),

            "hopefulness":
                self.hopefulness(text, lexicon),

            "societal_impact":
                self.societal_impact(
                    text,
                    entities,
                    lexicon,
                ),

            "inspirational_score":
                self.inspiration(
                    text,
                    sentiment,
                    lexicon,
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

    def readability(self, text, lexicon: Lexicon | None = None):

        lexicon = lexicon or lexicon_for(None)

        with _TEXTSTAT_LOCK:
            # Spanish uses the Fernandez-Huerta variant of Flesch; running
            # the English formula over Spanish text produced a number that
            # looked plausible and meant nothing.
            textstat.set_lang(lexicon.language)
            score = textstat.flesch_reading_ease(text)

        return round(

            max(
                0,
                min(score / 100, 1),
            ),

            4,
        )

    #######################################################

    def constructiveness(self, text, lexicon: Lexicon | None = None):

        lexicon = lexicon or lexicon_for(None)

        words = self._words(text)

        positive = count_matches(words, lexicon.constructive)

        negative = count_matches(words, lexicon.negative)

        return round(

            positive /
            (positive + negative + 1),

            4,
        )

    #######################################################

    def hopefulness(self, text, lexicon: Lexicon | None = None):

        lexicon = lexicon or lexicon_for(None)

        words = self._words(text)

        count = count_matches(words, lexicon.hope)

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
        lexicon: Lexicon | None = None,
    ):

        lexicon = lexicon or lexicon_for(None)

        words = self._words(text)

        score = 0

        score += count_matches(words, lexicon.societal)

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
        lexicon: Lexicon | None = None,
    ):

        lexicon = lexicon or lexicon_for(None)

        words = self._words(text)

        speculative = count_matches(words, lexicon.speculative)

        emotional = count_matches(words, lexicon.emotional)

        first_person = count_matches(words, lexicon.first_person)

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
        lexicon: Lexicon | None = None,
    ):

        lexicon = lexicon or lexicon_for(None)

        words = self._words(text)

        human = count_matches(words, lexicon.human)

        hope = self.hopefulness(text, lexicon)

        constructive = self.constructiveness(text, lexicon)

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