from __future__ import annotations

import re

from src.config.lexicons import Lexicon, count_matches, lexicon_for, matches
from src.config.settings import settings
from src.models.core.claim import Claim, ClaimFacts
from src.processors.nlp.entities import EntityExtractor

from .base import BaseProcessor


class ClaimExtractor(BaseProcessor):
    """
    Scores each sentence for check-worthiness and keeps the ones above
    the threshold.

    The signals (a named entity, a figure, a date, a unit, a reporting
    verb, a quote, enough length) are language-neutral; the *vocabulary*
    for two of them is not, and comes from the run's Lexicon. Before
    that, REPORTING_VERBS and the month names were English-only, so a
    Spanish article scored 0.20 lower on almost every sentence and
    yielded next to no claims - leaving the fact-checker nothing to
    check on 7 of the 12 configured sources.
    """

    WORD = re.compile(r"\b[^\W\d_]+\b", re.UNICODE)

    NUMBER_PATTERN = re.compile(r"\d+(?:[.,]\d+)?")

    YEAR_PATTERN = re.compile(r"\b\d{4}\b")

    # "%" is matched on its own, never inside a \b(...)\b group: it is not
    # a word character, so within one it could never match at all ("35%."
    # has no word boundary after the "%"). That silently cost every
    # percentage sentence 0.10 of its score - enough to push "The
    # treatment increased survival by 35%." below the claim threshold.
    PERCENT_PATTERN = re.compile(r"%")

    QUOTE_PATTERN = re.compile("[\"“”«»']")

    # A number with its percent sign attached, so `_facts` reports "35%"
    # rather than a bare 35 that means nothing on its own in a query.
    PERCENT_FIGURE = re.compile(r"\d+(?:[.,]\d+)?\s*%")

    # The *contents* of a quotation, for retaining what was said. The
    # single-character QUOTE_PATTERN above only answers "is there a quote
    # here at all", which is all _score needs.
    QUOTED_SPAN = re.compile(r"[\"“«]([^\"”»]{3,300})[\"”»]")

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
        language: str | None = None,
        opinion_max_score: float | None = None,
    ) -> list[Claim]:

        minimum = (
            min_confidence
            if min_confidence is not None
            else self.min_confidence
        )

        opinion_ceiling = (
            opinion_max_score
            if opinion_max_score is not None
            else settings.OPINION_MAX_SCORE
        )

        lexicon = lexicon_for(language)

        claims = []

        for sentence in self._split_sentences(text):

            entities = self.entity_extractor.process(sentence, entity_threshold)

            confidence = self._score(
                sentence,
                entities,
                lexicon,
            )

            if confidence < minimum:
                continue

            # Checked after the confidence floor, not before: scoring
            # opinion means another pass over the sentence, and most
            # sentences are already discarded by the line above.
            opinion = self._opinion_score(sentence, lexicon)

            if opinion > opinion_ceiling:
                continue

            claims.append(
                Claim(
                    text=sentence,
                    entities=entities,
                    confidence=round(confidence, 2),
                    facts=self._facts(sentence, lexicon),
                    opinion_score=round(opinion, 2),
                )
            )

        return claims

    ##########################################################

    def _opinion_score(self, sentence: str, lexicon: Lexicon) -> float:
        """
        How much of the sentence is evaluation rather than assertion,
        normalised by length so a long paragraph is not condemned by one
        stray adjective.

        Reuses `speculative` and `first_person` alongside the dedicated
        `opinion` set: a hedge ("could", "podría") and a first-person
        framing are opinion markers too, they were simply already in the
        lexicon under a different name for the objectivity score.
        """

        words = self._words(sentence)

        if not words:
            return 0.0

        hits = (
            count_matches(words, lexicon.opinion)
            + count_matches(words, lexicon.speculative)
            + count_matches(words, lexicon.first_person)
        )

        # Saturating rather than linear: three opinion markers in a
        # sentence is already decisive, and thirty words of otherwise
        # factual prose should not dilute that back below the ceiling.
        return min(hits / 3.0, 1.0)

    ##########################################################

    def _facts(self, sentence: str, lexicon: Lexicon) -> ClaimFacts:
        """
        The checkable components, kept as data. Every pattern here is
        already being run by _score to decide check-worthiness - this
        retains what it found instead of only counting it.
        """

        dates = self.YEAR_PATTERN.findall(sentence)

        words = self._words(sentence)

        dates += [word for word in words if matches(word, lexicon.month_names)]

        return ClaimFacts(
            # Percentages first so "35%" survives as one token rather than
            # being reported as the bare number 35.
            figures=self._figures(sentence),
            dates=dates,
            quotes=self.QUOTED_SPAN.findall(sentence),
        )

    ##########################################################

    def _figures(self, sentence: str) -> list[str]:

        figures = self.PERCENT_FIGURE.findall(sentence)

        covered = set(figures)

        for number in self.NUMBER_PATTERN.findall(sentence):
            if not any(number in figure for figure in covered):
                figures.append(number)

        return figures

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

    def _words(self, sentence: str) -> list[str]:

        return [word.lower() for word in self.WORD.findall(sentence)]

    ##########################################################

    def _score(
        self,
        sentence: str,
        entities,
        lexicon: Lexicon | None = None,
    ) -> float:

        lexicon = lexicon or lexicon_for(None)

        # Tokenised once and matched on whole words. The reporting-verb
        # check used to be a substring test over the raw sentence, so
        # "win" fired on "window" and "winter", and "m" (a unit) fired on
        # every word containing an m.
        words = self._words(sentence)

        score = 0.0

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
        # Dates - a four-digit year, a month name, or a
        # relative day, in the article's own language
        ##################################################

        if (
            self.YEAR_PATTERN.search(sentence)
            or count_matches(words, lexicon.month_names)
            or count_matches(words, lexicon.relative_dates)
        ):
            score += 0.15

        ##################################################
        # Measurements
        ##################################################

        if (
            self.PERCENT_PATTERN.search(sentence)
            or count_matches(words, lexicon.measurement_words)
        ):
            score += 0.10

        ##################################################
        # Reporting verbs
        ##################################################

        if count_matches(words, lexicon.reporting_verbs):
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
