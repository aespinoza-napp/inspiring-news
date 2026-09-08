from src.config.thresholds import PipelineThresholds
from src.services.fact_checker.claim_selector import ClaimSelector

from tests.factories import create_claim
from tests.fact_checker.fakes import FakeEmbeddingService


def test_select_empty_claims_returns_empty():

    selector = ClaimSelector(embeddings=FakeEmbeddingService())

    result = selector.select([])

    assert result.selected == []
    assert result.rejected == []


def test_select_orders_by_confidence_descending():

    claims = [
        create_claim(text="Low confidence claim.", confidence=0.5),
        create_claim(text="High confidence claim.", confidence=0.9),
        create_claim(text="Medium confidence claim.", confidence=0.7),
    ]

    selector = ClaimSelector(embeddings=FakeEmbeddingService())

    selected = selector.select(claims).selected

    assert [c.text for c in selected] == [
        "High confidence claim.",
        "Medium confidence claim.",
        "Low confidence claim.",
    ]


def test_select_caps_at_max_claims():
    """
    The cap arrives per call now. It used to be a class attribute frozen
    from settings at import time, which this test could only exercise by
    reaching in and reassigning it - meaning it never covered the path a
    real caller takes.
    """

    selector = ClaimSelector(embeddings=FakeEmbeddingService())

    claims = [
        create_claim(text=f"Claim number {i}.", confidence=0.9 - i * 0.01)
        for i in range(5)
    ]

    result = selector.select(
        claims,
        PipelineThresholds(max_claims_per_article=2),
    )

    assert len(result.selected) == 2
    assert result.selected[0].text == "Claim number 0."
    assert result.selected[1].text == "Claim number 1."

    assert [c.text for c in result.rejected] == [
        "Claim number 2.",
        "Claim number 3.",
        "Claim number 4.",
    ]
    assert all(c.reason == "exceeds_max_claims_cap" for c in result.rejected)


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

    result = selector.select(claims)

    assert [c.text for c in result.selected] == [
        "NASA discovered water on Mars.",
        "A completely unrelated claim.",
    ]

    assert [c.text for c in result.rejected] == ["NASA found water on Mars."]
    assert result.rejected[0].reason == "semantic_duplicate"


def test_select_skips_blank_claim_text():

    claims = [
        create_claim(text="   ", confidence=0.9),
        create_claim(text="A real claim.", confidence=0.5),
    ]

    selector = ClaimSelector(embeddings=FakeEmbeddingService())

    selected = selector.select(claims).selected

    assert [c.text for c in selected] == ["A real claim."]
