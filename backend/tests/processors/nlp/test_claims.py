"""
ClaimExtractor calls EntityExtractor.process() per sentence, which -
since the ML split - is a real HTTP call to inference/ rather than an
in-process GLiNER call. Tests that call .process() on non-empty text
need require_inference and skip when that service isn't reachable
(conftest.py). test_percentage_contributes_to_the_score calls the
scoring internals directly with pre-supplied entities, and
test_empty_text_yields_no_claims never reaches a sentence to extract
entities from - neither needs it.
"""

from src.config.lexicons import lexicon_for
from src.processors.nlp.claims import ClaimExtractor


def test_claim_extractor(require_inference):

    extractor = ClaimExtractor()

    text = (
        "OpenAI announced GPT-6 yesterday. "
        "The model improves reasoning by 40%. "
        "I really like artificial intelligence. "
        "Barcelona is beautiful."
    )

    claims = extractor.process(text)

    texts = [claim.text for claim in claims]

    assert isinstance(claims, list)

    # Both factual sentences carry a reporting verb plus a concrete
    # figure or date. The percentage sentence in particular only scores
    # high enough because MEASUREMENT_PATTERN can match "%" - it could
    # not before (the "%" alternative sat inside a ... group), which
    # dropped this claim silently.
    assert "OpenAI announced GPT-6 yesterday." in texts
    assert "The model improves reasoning by 40%." in texts

    # Opinion and aesthetic judgement are not check-worthy claims.
    assert "I really like artificial intelligence." not in texts
    assert "Barcelona is beautiful." not in texts

    assert all(0.0 < claim.confidence <= 1.0 for claim in claims)


def test_claim_with_numbers(require_inference):

    extractor = ClaimExtractor()

    claims = extractor.process("The treatment increased survival by 35%.")

    assert len(claims) == 1
    assert claims[0].confidence >= 0.50


def test_percentage_contributes_to_the_score():
    """
    Regression test for the unreachable "%" alternative in
    MEASUREMENT_PATTERN: the same sentence with and without a percent
    sign must not score identically.
    """

    extractor = ClaimExtractor()

    with_percent = extractor._score("Emissions fell by 35%.", {})
    without_percent = extractor._score("Emissions fell by 35.", {})

    assert with_percent > without_percent


def test_non_factual_text(require_inference):

    extractor = ClaimExtractor()

    text = "Wow! Amazing! Incredible! Nice weather today."

    assert extractor.process(text) == []


def test_empty_text_yields_no_claims():

    assert ClaimExtractor().process("") == []


# ----------------------------------------------------------------------
# Fact vs. opinion, and the facts kept as data
#
# These call the scoring internals directly with pre-supplied entities,
# so they need no inference service - same reasoning as
# test_percentage_contributes_to_the_score above.
# ----------------------------------------------------------------------


def test_opinion_sentences_score_above_factual_ones_in_english():
    """
    Nothing can be retrieved that confirms or refutes "this is a
    wonderful step" - putting it through retrieval only spends a search
    and an LLM call to arrive at UNVERIFIED.
    """

    extractor = ClaimExtractor()
    lexicon = lexicon_for("en")

    factual = extractor._opinion_score(
        "The grid ran on 50% renewable power in 2024.", lexicon
    )
    opinion = extractor._opinion_score(
        "We believe this is a wonderful and important step forward.", lexicon
    )

    assert factual < opinion
    assert factual <= 0.34


def test_opinion_sentences_score_above_factual_ones_in_spanish():
    """
    The Spanish lexicon has to carry this as completely as the English
    one. Seven of the twelve configured sources publish in Spanish, and
    a lexicon that only really works in English silently applies the
    filter to a minority of the corpus.
    """

    extractor = ClaimExtractor()
    lexicon = lexicon_for("es")

    factual = extractor._opinion_score(
        "La red funcionó con un 50% de energía renovable en 2024.", lexicon
    )
    opinion = extractor._opinion_score(
        "Creemos que es un avance maravilloso e importante.", lexicon
    )

    assert factual < opinion
    assert factual <= 0.34


def test_facts_retain_figures_dates_and_quotes():
    """
    Every pattern here was already being run to decide check-worthiness;
    the values were counted and thrown away. They are the most
    discriminative terms available when building a search query.
    """

    extractor = ClaimExtractor()

    facts = extractor._facts(
        'The minister said "we reached the target" after emissions fell 40% in 2024.',
        lexicon_for("en"),
    )

    assert "40%" in facts.figures
    # The percentage is kept whole - a bare "40" is an ignorable common
    # token in a web search, "40%" is not.
    assert "40" not in facts.figures
    assert "2024" in facts.dates
    assert facts.quotes == ["we reached the target"]
