"""
Which language an article is written in.

Deliberately a stopword-frequency count, not a model or a new
dependency. The corpus is en/es only (see `backend/data/sources/*.yaml`),
function words are the highest-signal, lowest-cost discriminator between
those two, and it runs in microseconds with no download and no state.
A learned detector would be more accurate on a three-word fragment; on a
news article body it would agree with this one essentially always.

What it is not: a general-purpose language identifier. Anything that is
not English or Spanish resolves to the fallback, which is correct
behaviour here - `lexicon_for()` scores an unknown language with the
English lexicon rather than failing the run.
"""

from __future__ import annotations

import re

from src.config.lexicons import DEFAULT_LANGUAGE, LEXICONS

WORD = re.compile(r"\b[^\W\d_]+\b", re.UNICODE)

# Below this many stopword hits the sample is too short to call, and the
# caller's fallback (the source's declared language) is better evidence
# than a coin flip on four words.
MIN_HITS = 4

# The winner must beat the runner-up by this ratio. English and Spanish
# share enough short tokens that a near-tie means "not sure", and a
# confident wrong answer here silently mis-scores a whole article.
MIN_RATIO = 1.25


class LanguageDetector:

    @staticmethod
    def detect(text: str, fallback: str | None = None) -> str:
        """
        The detected language, or `fallback` (default English) when the
        text is too short or too ambiguous to call.
        """

        default = fallback or DEFAULT_LANGUAGE

        if not text:
            return default

        # A few thousand characters is plenty and keeps this O(1) on
        # article length - stopword density does not change down the page.
        words = [word.lower() for word in WORD.findall(text[:4000])]

        if not words:
            return default

        scores = {
            language: sum(word in lexicon.stopwords for word in words)
            for language, lexicon in LEXICONS.items()
        }

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)

        best, best_hits = ranked[0]
        runner_up_hits = ranked[1][1] if len(ranked) > 1 else 0

        if best_hits < MIN_HITS:
            return default

        if runner_up_hits and best_hits < runner_up_hits * MIN_RATIO:
            return default

        return best
