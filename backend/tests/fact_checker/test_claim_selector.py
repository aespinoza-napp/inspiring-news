from src.services.fact_checker.claim_selector import ClaimSelector

from tests.factories import create_claim
from tests.fact_checker.fakes import FakeEmbeddingService


def test_select_empty_claims_returns_empty():

    selector = ClaimSelector(embeddings=FakeEmbeddingService())

    assert selector.select([]) == []


def test_select_orders_by_confidence_descending():

    claims = [
        create_claim(text="Low confidence claim.", confidence=0.5),
        create_claim(text="High confidence claim.", confidence=0.9),
        create_claim(text="Medium confidence claim.", confidence=0.7),
    ]

    selector = ClaimSelector(embeddings=FakeEmbeddingService())

    selected = selector.select(claims)

    assert [c.text for c in selected] == [
        "High confidence claim.",
        "Medium confidence claim.",
        "Low confidence claim.",
    ]


def test_select_caps_at_max_claims(monkeypatch):

    selector = ClaimSelector(embeddings=FakeEmbeddingService())
    selector.MAX_CLAIMS = 2

    claims = [
        create_claim(text=f"Claim number {i}.", confidence=0.9 - i * 0.01)
        for i in range(5)
    ]

    selected = selector.select(claims)

    assert len(selected) == 2
    assert selected[0].text == "Claim number 0."
    assert selected[1].text == "Claim number 1."


def test_select_drops_near_duplicate_claims():

    vector = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    embeddings = FakeEmbeddingService(vectors={
        "NASA discovered water on Mars.": vector,
        "NASA found water on Mars.": vector,
        "A completely unrelated claim.": [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    })

    claims = [
        create_claim(text="NASA discovered water on Mars.", confidence=0.9),
        create_claim(text="NASA found water on Mars.", confidence=0.8),
        create_claim(text="A completely unrelated claim.", confidence=0.7),
    ]

    selector = ClaimSelector(embeddings=embeddings)

    selected = selector.select(claims)

    assert [c.text for c in selected] == [
        "NASA discovered water on Mars.",
        "A completely unrelated claim.",
    ]


def test_select_skips_blank_claim_text():

    claims = [
        create_claim(text="   ", confidence=0.9),
        create_claim(text="A real claim.", confidence=0.5),
    ]

    selector = ClaimSelector(embeddings=FakeEmbeddingService())

    selected = selector.select(claims)

    assert [c.text for c in selected] == ["A real claim."]
