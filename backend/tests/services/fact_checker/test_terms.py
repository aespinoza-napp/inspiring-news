"""
What a claim is about, as terms.

Shared by query building and by lexical ranking, so a change here moves
both what is searched for and what counts as having been found - which
is the point: the two drifting apart is how retrieval came to ask for
one thing while scoring rewarded another.
"""

from src.services.fact_checker.claim_selector import ArticleContext
from src.services.fact_checker.terms import (
    anchor_terms,
    claim_terms,
    content_terms,
    coverage,
    fold,
    subject_terms,
)

from tests.factories import create_claim


def _coyote_claim():
    """
    The claim that motivated all of this. Its anchors are answerable by
    pages that have nothing to do with it; only its content words are not.
    """

    return create_claim(
        text=(
            "La obsesión del coyote por comprar los productos de ACME se "
            "tradujo en una representación del consumismo de Estados Unidos."
        ),
        entities={"ORG": ["ACME"], "LOC": ["Estados Unidos"]},
    )


def test_anchors_are_the_entities_figures_and_dates():

    claim = create_claim(
        text="NASA cut emissions by 40% in 2024.",
        entities={"ORG": ["NASA"]},
    )
    claim = claim.model_copy(update={
        "facts": claim.facts.model_copy(update={
            "figures": ["40%"],
            "dates": ["2024"],
        }),
    })

    assert anchor_terms(claim) == ["NASA", "40%", "2024"]


def test_content_terms_drop_stopwords_and_journalistic_noise():

    terms = content_terms(
        "Según el informe, la compañía dijo que mejoró sus emisiones",
        "es",
    )

    # "según", "informe" and "dijo" match every news page ever written.
    assert "según" not in terms
    assert "informe" not in terms
    assert "dijo" not in terms

    assert "compañía" in terms
    assert "mejoró" in terms
    assert "emisiones" in terms


def test_anchors_and_content_are_kept_disjoint():
    """
    An entity's own words survive content-word filtering, so "ACME" was
    counted once as an anchor and again as content - and anchors are
    weighted double. A page naming every entity and addressing nothing
    scored half marks, which is exactly the page the gate exists to cut.
    """

    anchors, content = claim_terms(_coyote_claim(), "es")

    assert anchors == ["ACME", "Estados Unidos"]

    lowered = {term.lower() for term in content}

    assert "acme" not in lowered
    assert "estados" not in lowered
    assert "unidos" not in lowered

    assert "consumismo" in lowered
    assert "coyote" in lowered


def test_a_page_with_every_name_and_none_of_the_assertion_scores_low():

    anchors, content = claim_terms(_coyote_claim(), "es")

    etymology = (
        "¿Qué significa ACME? La palabra acme proviene del griego y "
        "significa el punto más alto o culminación de algo. La marca "
        "aparece en Estados Unidos."
    )

    on_point = (
        "La obsesión del coyote por comprar productos de ACME se tradujo "
        "en una representación del consumismo de Estados Unidos."
    )

    assert coverage(etymology, anchors, content) < 0.5
    assert coverage(on_point, anchors, content) > 0.9


def test_coverage_folds_accents_before_comparing():
    """
    Spanish evidence carries both spellings of the same word, and every
    scraped page mangles at least one. Comparing unfolded loses real
    matches on exactly the language where recall is already thinner.
    """

    assert fold("representación") == "representacion"

    anchors, content = claim_terms(_coyote_claim(), "es")

    unaccented = (
        "La obsesion del coyote por comprar productos de ACME se tradujo "
        "en una representacion del consumismo de Estados Unidos."
    )

    assert coverage(unaccented, anchors, content) > 0.9


def test_a_multi_word_anchor_is_matched_as_a_phrase():

    claim = create_claim(
        text="La Segunda Guerra Mundial terminó.",
        entities={"EVENT": ["Segunda Guerra Mundial"]},
    )

    anchors, content = claim_terms(claim, "es")

    assert coverage("tras la Segunda Guerra Mundial", anchors, content) > 0.0
    assert coverage("una guerra mundial cualquiera", anchors, []) == 0.0


def test_a_claim_with_no_terms_covers_nothing():
    """
    Returning a perfect score for "there was nothing to look for" is how
    a gate stops gating.
    """

    assert coverage("any text at all", [], []) == 0.0


# ----------------------------------------------------------------------
# Restoring the article's subject to a sentence that lost it
# ----------------------------------------------------------------------


def _aura_claim():
    """
    Checked TRUE at 84%, confirmed by the Mexico City marathon's prize
    money. The article was about aura-farming battles; the sentence never
    says so, and it has an entity and a date of its own.
    """

    return create_claim(
        text=(
            "En agosto de 2026 ya había convocatorias en Ciudad de México "
            "con premios económicos."
        ),
        entities={"city": ["Ciudad de México"]},
    )


def _aura_context():

    # The article's real headline and its real yake keywords.
    return ArticleContext(
        title="Farmear aura: qué es y por qué se volvió viral en 2026",
        keywords=["farmear aura", "aura", "llevamos años", "farmear", "público"],
    )


def test_the_subject_is_the_headline_words_the_keywords_agree_on():

    # "volvió" and "viral" are in the headline but not what it is about.
    assert subject_terms(_aura_claim(), _aura_context(), "es") == ["Farmear", "aura"]


def test_no_subject_is_restored_to_a_claim_that_already_names_it():

    claim = create_claim(text="Las batallas de aura se multiplican en México.")

    assert subject_terms(claim, _aura_context(), "es") == []


def test_no_subject_is_restored_without_an_article():
    """POST /verify-claim checks a bare claim; there is nothing to restore."""

    assert subject_terms(_aura_claim(), None, "es") == []


def test_without_a_headline_the_top_keyword_stands_in():
    """
    Every article in the lake was extracted without a title for a while
    (trafilatura dropping metadata); the keywords were still right.
    """

    context = ArticleContext(title="", keywords=["farmear aura", "aura"])

    assert subject_terms(_aura_claim(), context, "es") == ["farmear", "aura"]


def test_the_restored_subject_leads_the_anchors():

    anchors, content = claim_terms(_aura_claim(), "es", _aura_context())

    assert anchors[:3] == ["Farmear", "aura", "Ciudad de México"]
    assert "convocatorias" in content


def test_a_page_about_the_right_city_and_the_wrong_event_covers_less():

    marathon = (
        "Maratón CDMX 2026: convocatorias y premios económicos en Ciudad de "
        "México para los primeros lugares."
    )

    without = coverage(marathon, *claim_terms(_aura_claim(), "es"))
    with_subject = coverage(marathon, *claim_terms(_aura_claim(), "es", _aura_context()))

    assert with_subject < without
