from src.processors.nlp import NLPProcessor


def test_claim_extraction(example_news):
    processor = NLPProcessor()

    claims = processor.process(example_news.content)

    assert len(claims) == 3
    assert claims[0].text.startswith("NASA")
    assert "NASA" in claims[0].entities