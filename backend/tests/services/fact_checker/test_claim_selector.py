from src.config.thresholds import PipelineThresholds
from src.models.core.claim import ClaimFacts
from src.services.fact_checker.claim_selector import ArticleContext, ClaimSelector

from tests.factories import create_claim
from tests.services.fact_checker.fakes import FakeEmbeddingService


def test_select_empty_claims_returns_empty():

    selector = ClaimSelector(embeddings=FakeEmbeddingService())

    result = selector.select([])

    assert result.selected == []
    assert result.rejected == []


def test_select_ranks_the_claim_central_to_the_article_first():
    """
    Selection answers "which claims is this article's credibility resting
    on", not "which sentences scored highest for check-worthiness". A
    high-confidence aside must lose to a claim that carries the article's
    own thesis.
    """

    on_thesis = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    off_thesis = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    context = ArticleContext(title="Spain reached 50% renewable power")

    embeddings = FakeEmbeddingService(vectors={
        context.thesis(): on_thesis,
        "Spain's grid ran on 50% renewables.": on_thesis,
        "The press office moved to a new building.": off_thesis,
    })

    claims = [
        # Higher extraction confidence, but not what the article is about.
        create_claim(
            text="The press office moved to a new building.",
            confidence=0.95,
            entities={},
        ),
        create_claim(
            text="Spain's grid ran on 50% renewables.",
            confidence=0.6,
            entities={},
        ),
    ]

    selector = ClaimSelector(embeddings=embeddings)

    selected = selector.select(claims, context=context).selected

    assert [c.text for c in selected] == [
        "Spain's grid ran on 50% renewables.",
        "The press office moved to a new building.",
    ]


def test_select_scores_concrete_claims_above_vague_ones():
    """
    Specificity is part of being load-bearing: a claim carrying a figure
    and a date can actually be checked, an unquantified assertion mostly
    cannot.
    """

    selector = ClaimSelector(embeddings=FakeEmbeddingService())

    vague = create_claim(text="Emissions fell across the sector.", entities={})
    concrete = create_claim(
        text="Emissions fell 40% in 2024.",
        entities={},
    ).model_copy(update={"facts": ClaimFacts(figures=["40%"], dates=["2024"])})

    selected = selector.select([vague, concrete]).selected

    assert selected[0].text == "Emissions fell 40% in 2024."
    assert selected[0].anchor_score > selected[1].anchor_score


def test_select_caps_at_the_anchor_band():
    """
    The band arrives per call. Verifying the two-to-four claims the
    article rests on is the point - checking the five highest-scoring
    sentences is what this replaced.
    """

    selector = ClaimSelector(embeddings=FakeEmbeddingService())

    claims = [
        create_claim(text=f"Claim number {i}.", confidence=0.9 - i * 0.01)
        for i in range(5)
    ]

    result = selector.select(
        claims,
        PipelineThresholds(anchor_claims_max=2),
    )

    assert len(result.selected) == 2
    assert len(result.rejected) == 3
    assert all(c.reason == "outside_anchor_band" for c in result.rejected)


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
