"""
What the draft review needs to know about the language a draft is
written in: how to prepare its text for the keyword lexicons, which
readability formula it is measured with, and whether a text is still in
it.

A draft's language is declared (`ArticleDraft.language`), never
detected: LanguageDetector tells English from Spanish only, and would
call a Catalan draft one or the other. So every function here takes the
language - and the Lexicon - it is given.

**Catalan.** It has a complete lexicon (src/config/lexicons.py,
`CATALAN`), but no readability formula of its own: textstat has none,
and none validated for Catalan was found to cite. Asked for "ca",
textstat's Flesch reading ease silently uses the *English* constants
over Catalan syllables (206.835 - 1.015 ASL - 84.6 ASW), which scored a
plain two-sentence Catalan text 61 where the Spanish formula gives 100.
So Catalan is measured with an explicitly named stand-in: the
Fernández-Huerta formula, fitted to Spanish - the closest language the
literature covers - over Catalan syllable counts (Pyphen's Catalan
hyphenation dictionary). The metric's summary says so on every review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import textstat

from src.config.lexicons import Lexicon
from src.processors.nlp.quality import QualityAnalyzer, _TEXTSTAT_LOCK

LANGUAGE_NAMES = {"ca": "Catalan", "es": "Spanish", "en": "English"}

WORD = re.compile(r"\b[\w'-]+\b")


@dataclass(frozen=True)
class ReadabilityFormula:

    name: str

    # Where the formula comes from, for the summary a person reads.
    source: str

    # True when the formula was not fitted to this language and stands in
    # for one that would be.
    stand_in: bool = False


FLESCH = ReadabilityFormula(
    name="Flesch reading ease",
    source="Flesch, R. (1948). A new readability yardstick. Journal of Applied Psychology, 32(3), 221-233",
)

FERNANDEZ_HUERTA = ReadabilityFormula(
    name="Fernández-Huerta reading ease",
    source="Fernández Huerta, J. (1959). Medidas sencillas de lecturabilidad. Consigna, 214, 29-32",
)

READABILITY: dict[str, ReadabilityFormula] = {
    "en": FLESCH,
    # textstat's "es" Flesch constants (206.84, 1.02, 60) are
    # Fernández-Huerta's, so this is what QualityAnalyzer already runs.
    "es": FERNANDEZ_HUERTA,
    "ca": ReadabilityFormula(
        name=FERNANDEZ_HUERTA.name,
        source=FERNANDEZ_HUERTA.source,
        stand_in=True,
    ),
}


def language_name(language: str) -> str:

    return LANGUAGE_NAMES.get(language, language)


# ----------------------------------------------------------------------
# Preparing text for the word lists
# ----------------------------------------------------------------------

# Catalan's geminated l: "col·laboració". `·` is not a word character, so
# without this the tokeniser yields "col" and "laboració". Some writers
# type a full stop for it ("col.laboració"); only between lowercase l's,
# so a missing space after a sentence ("hotel.Llavors") is left alone.
_PUNT_VOLAT = re.compile(r"(?<=l)[·.](?=l)|(?<=L)·(?=L)")

# Elided articles and pronouns: "d'investigació", "l'escola", "s'ha". The
# tokeniser keeps "'" inside a word, so the whole thing would be one token
# and no prefix entry would match the noun. The typographic apostrophe
# (’) is not a word character and already splits.
_ELISION = re.compile(r"\b([dlsmntDLSMNT])'(?=\w)")


def prepare_for_scoring(text: str, language: str) -> str:
    """The text as the lexicon's entries expect to see it."""

    if language != "ca":
        return text

    return _ELISION.sub(r"\1 ", _PUNT_VOLAT.sub("", text))


# ----------------------------------------------------------------------
# Readability
# ----------------------------------------------------------------------


def readability(text: str, language: str, lexicon: Lexicon, quality_analyzer: QualityAnalyzer) -> float:
    """
    Reading ease on 0-1 (higher = easier), as QualityAnalyzer reports it.

    English and Spanish go through QualityAnalyzer exactly as /correct
    and the pipeline do. Catalan is the stand-in described above:
    textstat's `fernandez_huerta` with the language set to "ca", which
    keeps Fernández-Huerta's coefficients and counts syllables with the
    Catalan dictionary. Under QualityAnalyzer's lock, because
    `textstat.set_lang` is process-global.
    """

    if language != "ca":
        return quality_analyzer.readability(text, lexicon)

    with _TEXTSTAT_LOCK:
        textstat.set_lang("ca")
        score = textstat.fernandez_huerta(text)

    return round(max(0.0, min(score / 100, 1.0)), 4)


def readability_summary(language: str) -> str:

    formula = READABILITY[language]
    name = language_name(language)

    if formula.stand_in:
        return (
            f"Stand-in for {name}: {formula.name}, a formula fitted to Spanish, over "
            f"{name} syllable counts. No reading-ease formula validated for {name} is "
            "available here, so read this as indicative, not calibrated. Scaled to "
            f"0-100 (higher = easier to read). {formula.source}."
        )

    return f"{formula.name}, scaled to 0-100 (higher = easier to read). {formula.source}."


# ----------------------------------------------------------------------
# Is a text still in its language?
# ----------------------------------------------------------------------


def stopword_share(text: str, lexicon: Lexicon) -> float:
    """
    The share of `text`'s words that are `lexicon`'s stopwords. Compared
    between a draft and the corrector's proposal, it shows a proposal
    that came back translated - a model's habit with a Catalan draft -
    without telling Catalan from Spanish outright, which those stopword
    sets are too small to do on their own.
    """

    words = [word.lower() for word in WORD.findall(prepare_for_scoring(text, lexicon.language))]

    if not words:
        return 0.0

    return sum(word in lexicon.stopwords for word in words) / len(words)
