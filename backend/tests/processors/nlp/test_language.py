"""
The language detector, and the two processors that branch on it.

These exist because the pipeline scored every article with English word
lists and the English readability formula while 7 of the 12 configured
sources publish in Spanish - so constructiveness, hopefulness and
inspiration collapsed toward zero for the majority of the corpus, the
admission filter rejected it, and claim extraction found nothing for the
fact-checker to check.
"""

import pytest

from src.config.lexicons import (
    LEXICONS,
    SUPPORTED_LANGUAGES,
    count_matches,
    lexicon_for,
    matches,
)
from src.processors.nlp.claims import ClaimExtractor
from src.processors.nlp.language import LanguageDetector
from src.processors.nlp.quality import QualityAnalyzer

SPANISH_TEXT = (
    "Los investigadores del hospital universitario anunciaron un tratamiento "
    "innovador que mejoró la recuperación de los pacientes. El proyecto, una "
    "colaboración internacional, redujo la mortalidad y ofrece esperanza a "
    "miles de familias."
)

ENGLISH_TEXT = (
    "Researchers at the university hospital announced an innovative treatment "
    "that improved patient recovery. The project, an international "
    "collaboration, reduced mortality and offers hope to thousands of families."
)


# ----------------------------------------------------------------------
# Detection
# ----------------------------------------------------------------------


def test_detects_spanish():
    assert LanguageDetector.detect(SPANISH_TEXT) == "es"


def test_detects_english():
    assert LanguageDetector.detect(ENGLISH_TEXT) == "en"


def test_empty_text_returns_the_fallback():
    assert LanguageDetector.detect("", fallback="es") == "es"
    assert LanguageDetector.detect("") == "en"


def test_text_with_no_words_returns_the_fallback():
    assert LanguageDetector.detect("12345 !!! ---", fallback="es") == "es"


def test_too_few_stopwords_to_call_returns_the_fallback():
    """
    A three-word fragment carries no evidence. Guessing from it would
    mis-score a whole article, so the source's declared language wins.
    """

    assert LanguageDetector.detect("NASA water Mars", fallback="es") == "es"


def test_an_ambiguous_sample_returns_the_fallback():
    """
    Text mixing both languages should decline to choose rather than pick
    a winner by one token.
    """

    mixed = "the of and in is that for con para se su sus al lo como más"

    assert LanguageDetector.detect(mixed, fallback="es") == "es"


def test_detection_reads_only_the_head_of_a_long_article():
    """
    Stopword density does not change down the page, so detection is
    capped to keep it O(1) in article length.
    """

    assert LanguageDetector.detect(SPANISH_TEXT + " palabra" * 50_000) == "es"


# ----------------------------------------------------------------------
# Lexicons
# ----------------------------------------------------------------------


def test_both_supported_languages_are_available():
    assert SUPPORTED_LANGUAGES == {"en", "es"}


def test_an_unsupported_language_falls_back_to_english():
    """
    Falls back rather than raising: an unexpected language should score
    an article conservatively, not fail the run for it.
    """

    assert lexicon_for("fr").language == "en"
    assert lexicon_for(None).language == "en"
    assert lexicon_for("").language == "en"


def test_a_regional_tag_resolves_to_its_base_language():
    assert lexicon_for("es-ES").language == "es"
    assert lexicon_for("EN-GB").language == "en"


def test_star_entries_match_as_prefixes():
    """
    Spanish is far more inflected than English (mejorar / mejora /
    mejoró / mejorado), so exact-token sets would give it a fraction of
    English's recall and quietly reintroduce the bias.
    """

    vocabulary = frozenset({"mejor*", "guerra"})

    assert matches("mejoró", vocabulary)
    assert matches("mejorado", vocabulary)
    assert matches("guerra", vocabulary)
    assert not matches("guerras", vocabulary)
    assert not matches("peor", vocabulary)


def test_count_matches_counts_every_hit():
    assert count_matches(["mejoró", "mejorado", "casa"], frozenset({"mejor*"})) == 2


@pytest.mark.parametrize("language", sorted(SUPPORTED_LANGUAGES))
def test_every_lexicon_fills_every_word_set(language):
    """
    A half-filled lexicon scores its language as though the missing
    signals never occur - which is exactly the failure being fixed.
    """

    lexicon = LEXICONS[language]

    for field in (
        "speculative", "emotional", "first_person", "constructive",
        "negative", "hope", "human", "societal", "reporting_verbs",
        "month_names", "relative_dates", "measurement_words", "stopwords",
    ):
        assert getattr(lexicon, field), f"{language}.{field} is empty"


def test_every_lexicon_has_twelve_months(language="es"):
    for code, lexicon in LEXICONS.items():
        # Spanish carries "setiembre" as an accepted variant of September.
        assert len(lexicon.month_names) >= 12, code


# ----------------------------------------------------------------------
# Quality scoring branches on language
# ----------------------------------------------------------------------


def test_spanish_text_scores_like_english_when_given_its_own_lexicon():
    """
    The headline regression. The same story in two languages should get
    comparable constructiveness - it used to get 0.875 and 0.0.
    """

    analyzer = QualityAnalyzer()

    spanish = analyzer.process(SPANISH_TEXT, language="es")
    english = analyzer.process(ENGLISH_TEXT, language="en")

    assert spanish["constructiveness"] == pytest.approx(
        english["constructiveness"], abs=0.15
    )
    assert spanish["hopefulness"] > 0.0
    assert spanish["inspirational_score"] > 0.0


def test_spanish_text_scored_as_english_loses_its_keyword_signal():
    """
    Pins the bug itself, so a future refactor that drops the language
    argument fails here instead of silently rejecting Spanish articles.
    """

    analyzer = QualityAnalyzer()

    as_spanish = analyzer.process(SPANISH_TEXT, language="es")
    as_english = analyzer.process(SPANISH_TEXT, language="en")

    assert as_english["constructiveness"] == 0.0
    assert as_english["hopefulness"] == 0.0
    assert as_spanish["constructiveness"] > 0.5


def test_readability_uses_the_language_specific_formula():
    """
    Spanish uses the Fernandez-Huerta variant of Flesch; running the
    English formula over Spanish produced a plausible-looking number
    that meant nothing.
    """

    analyzer = QualityAnalyzer()

    assert analyzer.process(SPANISH_TEXT, language="es")["readability"] != (
        analyzer.process(SPANISH_TEXT, language="en")["readability"]
    )


def test_quality_defaults_to_english_when_no_language_is_given():
    analyzer = QualityAnalyzer()

    assert analyzer.process(ENGLISH_TEXT) == analyzer.process(
        ENGLISH_TEXT, language="en"
    )


def test_sentiment_actually_reaches_the_inspiration_metric():
    """
    QualityAnalyzer accepted a `sentiment` argument the pipeline never
    passed, so inspiration was scored against a hardcoded 0.5 positivity
    for every article ever analysed.
    """

    from src.models.nlp.sentiment_result import SentimentResult

    def sentiment(positive):
        return SentimentResult(
            label="positive", positive=positive, neutral=1 - positive,
            negative=0.0, polarity=positive, subjectivity=0.2,
            confidence=0.9, emotional_intensity=0.3,
        )

    analyzer = QualityAnalyzer()

    high = analyzer.process(ENGLISH_TEXT, sentiment=sentiment(1.0))
    low = analyzer.process(ENGLISH_TEXT, sentiment=sentiment(0.0))

    assert high["inspirational_score"] > low["inspirational_score"]


# ----------------------------------------------------------------------
# Claim extraction branches on language
# ----------------------------------------------------------------------


def test_a_spanish_claim_scores_above_the_threshold_in_spanish():

    extractor = ClaimExtractor()

    sentence = "Los investigadores anunciaron que el tratamiento aumentó la supervivencia un 35%."

    assert extractor._score(sentence, {}, lexicon_for("es")) >= 0.50


def test_the_same_spanish_claim_is_dropped_when_scored_as_english():

    extractor = ClaimExtractor()

    sentence = "Los investigadores anunciaron que el tratamiento aumentó la supervivencia un 35%."

    assert extractor._score(sentence, {}, lexicon_for("en")) < 0.50


def test_spanish_month_names_count_as_a_date():

    extractor = ClaimExtractor()

    with_month = "El estudio se publicó en septiembre con datos nuevos."
    without = "El estudio se publicó con datos nuevos."

    assert extractor._score(with_month, {}, lexicon_for("es")) > extractor._score(
        without, {}, lexicon_for("es")
    )


def test_reporting_verbs_match_whole_words_not_substrings():
    """
    The check used to be a substring test over the raw sentence, so
    "win" fired on "window" and "winter".
    """

    extractor = ClaimExtractor()

    assert extractor._score("The window was open in winter.", {}) == 0.0
