from src.processors.nlp.claims import ClaimExtractor


def test_claim_extractor():

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


def test_claim_with_numbers():

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


def test_non_factual_text():

    extractor = ClaimExtractor()

    text = "Wow! Amazing! Incredible! Nice weather today."

    assert extractor.process(text) == []


def test_empty_text_yields_no_claims():

    assert ClaimExtractor().process("") == []
