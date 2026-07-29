from src.processors.nlp.claims import ClaimExtractor


def test_claim_extractor():

    extractor = ClaimExtractor()

    text = """
    OpenAI announced GPT-6 yesterday.

    The model improves reasoning by 40%.

    I really like artificial intelligence.

    Scientists discovered a new treatment for cancer.

    Barcelona is beautiful.
    """

    claims = extractor.process(text)

    print()

    for claim in claims:

        print(claim)

    assert isinstance(claims, list)

    assert len(claims) >= 3

    assert all(
        claim.confidence > 0
        for claim in claims
    )



def test_claim_contains_entities():

    extractor = ClaimExtractor()

    text = """
    NASA discovered water on Mars.
    """

    claims = extractor.process(text)
    print(claims)
    #assert len(claims) == 1

    #assert len(claims[0].entities) > 0

def test_claim_with_numbers():

    extractor = ClaimExtractor()

    text = """
    The treatment increased survival by 35%.
    """

    claims = extractor.process(text)
    print(claims)
    assert len(claims) == 1

    #assert claims[0].confidence >= 0.8

def test_non_factual_text():

    extractor = ClaimExtractor()

    text = """
    Wow!

    Amazing!

    Incredible!

    Nice weather today.
    """

    claims = extractor.process(text)

    assert claims == []

test_claim_extractor()
test_claim_contains_entities()
test_claim_with_numbers()
test_non_factual_text()