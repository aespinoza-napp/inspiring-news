"""
The queries a claim is searched with, when it comes from an article.

The anchor query used to restore the article's subject only when the
claim named no entity at all. An entity is not the subject: "convocatorias
en Ciudad de México con premios económicos" names a city, so it was
searched as the city - and found the marathon.
"""

from src.services.fact_checker.claim_selector import ArticleContext
from src.services.fact_checker.retrieval.query_builder import QueryKind, plan_queries

from tests.factories import create_claim


def _aura_claim():

    claim = create_claim(
        text=(
            "En agosto de 2026 ya había convocatorias en Ciudad de México "
            "con premios económicos."
        ),
        entities={"city": ["Ciudad de México"]},
    )

    return claim.model_copy(update={
        "facts": claim.facts.model_copy(update={
            "figures": ["2026"],
            "dates": ["2026", "agosto"],
        }),
    })


def _context():

    # The article's real headline and its real yake keywords.
    return ArticleContext(
        title="Farmear aura: qué es y por qué se volvió viral en 2026",
        keywords=["farmear aura", "aura", "llevamos años", "farmear", "público"],
    )


def test_every_query_carries_the_subject_the_sentence_lost():

    plan = plan_queries(_aura_claim(), _context(), "es")

    assert {query.kind for query in plan} == set(QueryKind)

    for query in plan:
        assert "Farmear aura" in query.text, query


def test_the_proposition_asks_for_the_subject_and_the_assertion_together():

    [proposition] = [
        query
        for query in plan_queries(_aura_claim(), _context(), "es")
        if query.kind == QueryKind.PROPOSITION
    ]

    assert proposition.text.startswith("Farmear aura ")
    assert "convocatorias" in proposition.text


def test_a_claim_without_an_article_is_searched_as_it_stands():

    [anchor, *_] = plan_queries(_aura_claim(), None, "es")

    assert anchor.text.startswith("Ciudad de México")
    assert "aura" not in anchor.text.lower()
