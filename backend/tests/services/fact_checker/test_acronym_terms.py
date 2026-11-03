"""
Acronyms are terms (src/services/fact_checker/terms.py, 2026-11-03).

Every claim of an article on South Africa's HPV vaccination came back
UNVERIFIED citing arXiv papers: "HPV" is three letters, under the 4-letter
floor for a content word, and the entity model had not tagged it - so no
query asked for it.
"""

from src.models.core.claim import Claim, ClaimFacts
from src.services.fact_checker.retrieval.query_builder import build_proposition_query, build_query
from src.services.fact_checker.terms import acronyms, anchor_terms, claim_terms, content_terms

HPV = Claim(
    text="Since October 2024, South Africa has adopted a single-dose HPV vaccination approach.",
    entities={"LOC": ["South Africa"]},
    confidence=0.8,
    facts=ClaimFacts(figures=["2024"], dates=["2024"]),
)


def test_an_acronym_is_a_content_word():

    assert "HPV" in content_terms(HPV.text, "en")


def test_an_acronym_whose_lower_case_is_a_stopword_is_kept():

    assert content_terms("The WHO and the US agreed.", "en")[:2] == ["WHO", "US"]


def test_short_lower_case_words_still_are_not():

    assert content_terms("it was a big day for us", "en") == []


def test_an_acronym_is_an_anchor_not_also_content():

    anchors, content = claim_terms(HPV, "en")

    assert "HPV" in anchors and "HPV" not in content


def test_an_acronym_inside_an_entity_is_not_repeated():

    assert acronyms("The NHS said so.", ["NHS England"]) == []
    assert anchor_terms(Claim(text="NASA found water.", entities={"ORG": ["NASA"]}, confidence=0.8)) == ["NASA"]


def test_the_anchor_query_names_the_subject_and_asks_the_year_once():

    assert build_query(HPV) == 'South Africa HPV "2024"'


def test_the_proposition_query_carries_it():

    assert "HPV" in build_proposition_query(HPV, language="en").split()
