"""
Whether a source says anything of its own (fact_checker/independence.py),
from what the train half and the two real articles of 2026-11-03 showed.
"""

import pytest

from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim
from src.models.fact_checker.fact_check import Verdict
from src.services.fact_checker.claim_selector import ClaimSelector
from src.services.fact_checker.fact_checker import FactChecker
from src.services.fact_checker.independence import compare, decisive_altered, sort_sources
from src.services.fact_checker.verification.confidence_scorer import ConfidenceScorer
from src.services.fact_checker.verification.llm_verification import LLMVerificationResult

from tests.factories import create_article, create_evidence
from tests.services.fact_checker.fakes import FakeEmbeddingService, FakeEvidenceRetriever, FakeRanker, FakeVerifier

CLAIM = "Jire carried the lifeless body of her one-year-old infant for some 168 kilometres to reach the clinic."

ORIGINAL = "Jire carried the lifeless body of her one-year-old infant for some 68 kilometres to reach the clinic."


def claim(text=CLAIM):
    return Claim(text=text, entities={}, confidence=0.8)


# ----------------------------------------------------------------------
# Reading one source
# ----------------------------------------------------------------------


def test_the_sentence_word_for_word_is_a_copy():

    assert compare(CLAIM, f"Read this. {CLAIM} And more.").relation == "copy"


def test_punctuation_and_accents_do_not_make_it_a_different_sentence():

    assert compare("La nave amerizó con éxito este lunes en el océano Pacífico frente a Australia.",
                   "La nave amerizo, con exito, este lunes en el oceano Pacifico frente a Australia").relation == "copy"


def test_one_changed_figure_is_an_altered_detail_and_says_what_changed():

    found = compare(CLAIM, f"The report opens here. {ORIGINAL} It goes on.")

    assert found.relation == "altered"
    assert found.changes == [("168", "68")]
    assert found.sentence == ORIGINAL


def test_one_changed_word_is_an_altered_detail():

    found = compare(
        "An MIT report on AI and education published this spring found that most teachers used it weekly.",
        "An MIT report on AI and education published this summer found that most teachers used it weekly.",
    )

    assert found.changes == [("spring", "summer")]


@pytest.mark.parametrize("source", [
    # An inflection is the same word.
    "An MIT report on AI and education published this spring finds that most teachers used it weekly.",
    # A function word changes no fact.
    "An MIT report on AI and education published in spring found that most teachers used it weekly.",
    # A rewording, longer than a detail: left to the model.
    "A report by MIT says that this spring a large share of the teachers were using AI on a weekly basis.",
    # Another sentence on the same subject.
    "MIT published a report on AI and education this spring.",
])
def test_what_is_not_a_changed_detail(source):

    found = compare(
        "An MIT report on AI and education published this spring found that most teachers used it weekly.",
        source,
    )

    assert found.relation == "independent"


def test_a_short_sentence_can_be_written_twice_independently():

    assert compare("El Gobierno lo aprobó ayer.", "El Gobierno lo aprobó ayer.").relation == "independent"


def test_nothing_to_read_is_independent():

    assert compare(CLAIM, None).relation == "independent"


# ----------------------------------------------------------------------
# Sorting the evidence
# ----------------------------------------------------------------------


def test_copies_leave_with_their_reason_and_the_order_stays():

    first, copy, last = (
        create_evidence(url="https://a.example/1", content="Nothing like it."),
        create_evidence(url="https://b.example/2", content=CLAIM),
        create_evidence(url="https://c.example/3", content="Nothing like it either."),
    )

    found = sort_sources(claim(), [first, copy, last])

    assert [item.url for item in found.kept] == [first.url, last.url]
    assert found.copies[0].url == copy.url
    assert "word for word" in found.copies[0].reason


def test_a_restated_claim_is_compared_by_the_sentence_it_came_from():

    restated = claim("Jire walked 168 kilometres.").model_copy(update={"written_as": CLAIM})

    assert sort_sources(restated, [create_evidence(content=CLAIM)]).copies


def test_a_copy_beside_an_altered_page_settles_nothing():
    """Outlets disagree about the detail: counting copies of a sentence does not settle it."""

    altered = create_evidence(url="https://a.example/1", content=ORIGINAL)
    copy = create_evidence(url="https://b.example/2", content=CLAIM)

    found = sort_sources(claim(), [altered, copy])

    assert found.altered and found.copies
    assert decisive_altered(found, found.kept) == []


# ----------------------------------------------------------------------
# In the pipeline
# ----------------------------------------------------------------------


def checker_for(repository, evidence, verifier):

    return FactChecker(
        repository,
        claim_selector=ClaimSelector(embeddings=FakeEmbeddingService(vectors={CLAIM: [1.0] + [0.0] * 7})),
        evidence_retriever=FakeEvidenceRetriever({CLAIM: evidence}),
        ranker=FakeRanker(),
        verifier=verifier,
        confidence_scorer=ConfidenceScorer(),
    )


@pytest.mark.usefixtures("list_verifier")
def test_an_altered_detail_is_false_without_asking_the_model(repository):

    verifier = FakeVerifier({})

    report = checker_for(
        repository,
        [create_evidence(url="https://a.example/1", domain="a.example", content=ORIGINAL)],
        verifier,
    ).run(create_article(claims=[claim()]))

    [check] = report.claim_checks

    assert check.verdict == Verdict.FALSE
    assert verifier.timeouts == []
    assert '"68" where the claim says "168"' in check.explanation
    assert check.evidence[0].quote == ORIGINAL


@pytest.mark.usefixtures("list_verifier")
def test_a_copy_is_not_counted_and_is_listed_as_rejected(repository):

    verifier = FakeVerifier({
        CLAIM: LLMVerificationResult(verdict=Verdict.UNVERIFIED, confidence=0.0, explanation="Nothing."),
    })

    report = checker_for(
        repository,
        [create_evidence(url="https://copy.example/1", domain="copy.example", content=CLAIM)],
        verifier,
    ).run(create_article(claims=[claim()]))

    [check] = report.claim_checks

    assert check.evidence == []
    assert any("word for word" in rejected.reason for rejected in check.rejected_sources)


@pytest.mark.usefixtures("list_verifier")
def test_off_keeps_the_pipeline_as_it_was(repository):

    evidence = [create_evidence(url="https://copy.example/1", domain="copy.example", content=CLAIM)]

    verifier = FakeVerifier({
        CLAIM: LLMVerificationResult(verdict=Verdict.TRUE, confidence=0.9, explanation="Yes.", cited_evidence=[0]),
    })

    report = checker_for(repository, evidence, verifier).run(
        create_article(claims=[claim()]),
        thresholds=PipelineThresholds(evidence_independence=False),
    )

    assert report.claim_checks[0].verdict == Verdict.TRUE
