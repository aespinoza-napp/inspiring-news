"""
A claim restated as something checkable on its own
(src/services/fact_checker/restatement.py), built from the sentence that
was searched as `Samuda Jamaica "30"`.
"""

import pytest

from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim, ClaimFacts
from src.models.fact_checker.fact_check import Verdict
from src.services.fact_checker.claim_selector import ArticleContext, ClaimSelector
from src.services.fact_checker.fact_checker import FactChecker
from src.services.fact_checker.restatement import ClaimRestater, validate, working_claim
from src.services.fact_checker.verification.confidence_scorer import ConfidenceScorer
from src.services.fact_checker.verification.llm_verification import LLMVerificationResult
from src.services.llms import LLMUnavailableError

from tests.factories import create_article, create_evidence
from tests.services.fact_checker.fakes import FakeEmbeddingService, FakeEvidenceRetriever, FakeRanker, FakeVerifier

SAMUDA = Claim(
    text=(
        "Samuda argued Jamaica was different because, although the country had "
        "“conquered our crime monster”, it had “spent 30 years being in the top three "
        "most murderous countries on the planet”."
    ),
    entities={"PERSON": ["Samuda"], "LOC": ["Jamaica"]},
    confidence=0.8,
    facts=ClaimFacts(figures=["30"]),
)

CONTEXT = ArticleContext(
    title="Jamaica's environment minister Matthew Samuda rejects calls to legalise ...",
    lead="Jamaica's minister Matthew Samuda told the summit in Belém on Monday ...",
)

CHECKABLE = "Jamaica spent 30 years among the three countries with the highest murder rates in the world."

ANSWER = {
    "kind": "attributed",
    "speaker": "Matthew Samuda, Jamaica's minister",
    "standalone": "Jamaica's minister Matthew Samuda argued that Jamaica had spent 30 years among the three most murderous countries.",
    "checkable": CHECKABLE,
    "questions": ["Was Jamaica among the three highest murder rates for 30 years?"],
}


class StubClient:

    def __init__(self, answer=None, raises=None):
        self.answer = answer
        self.raises = raises
        self.prompts = []

    def complete_json(self, system_prompt, user_prompt, max_retries=1, max_tokens=None, timeout=None):
        self.prompts.append(user_prompt)
        if self.raises:
            raise self.raises
        return self.answer


# ----------------------------------------------------------------------
# The answer, held to the sentence
# ----------------------------------------------------------------------


def test_reported_speech_is_checked_as_the_fact_inside_it():

    restated = ClaimRestater(StubClient(ANSWER)).restate(SAMUDA, CONTEXT, "en")

    assert restated.used and restated.kind == "attributed"
    assert restated.checkable == CHECKABLE
    assert restated.speaker.startswith("Matthew Samuda")


def test_the_model_sees_the_headline_the_opening_and_the_sentence():

    client = StubClient(ANSWER)
    ClaimRestater(client).restate(SAMUDA, CONTEXT, "en")

    assert "Headline: Jamaica's environment minister" in client.prompts[0]
    assert "Opening: Jamaica's minister Matthew Samuda" in client.prompts[0]
    assert "Sentence: Samuda argued" in client.prompts[0]


def test_an_invented_figure_is_refused():

    restated = validate({**ANSWER, "checkable": "Jamaica had 1,500 murders a year for 30 years."}, SAMUDA, CONTEXT, "en")

    assert not restated.used
    assert restated.checkable == SAMUDA.text
    assert "1.500" in restated.note


def test_a_figure_from_the_article_is_not_invented():

    context = ArticleContext(title=CONTEXT.title, lead="Jamaica recorded 1,500 murders in 2009.")

    assert validate({**ANSWER, "checkable": "Jamaica recorded 1,500 murders in 2009 after 30 years of high rates."}, SAMUDA, context, "en").used


def test_a_restatement_about_something_else_is_refused():

    elsewhere = "The summit in Belém opened on Monday with forty speeches."

    restated = validate({**ANSWER, "checkable": elsewhere, "standalone": elsewhere}, SAMUDA, CONTEXT, "en")

    assert not restated.used and restated.checkable == SAMUDA.text


def test_an_opinion_is_checked_as_written_but_its_reading_is_kept():

    claim = Claim(text="Samuda argued Jamaica was different from every other island.", entities={}, confidence=0.8)

    restated = validate({**ANSWER, "kind": "opinion", "checkable": claim.text}, claim, CONTEXT, "en")

    assert not restated.used and restated.kind == "opinion"
    assert restated.checkable == claim.text and restated.speaker


@pytest.mark.parametrize("answer", [None, {}, {"kind": "fact", "checkable": "short"}])
def test_no_usable_answer_checks_the_sentence(answer):

    assert not validate(answer, SAMUDA, CONTEXT, "en").used


def test_a_model_that_is_down_never_fails_the_claim():

    restated = ClaimRestater(StubClient(raises=LLMUnavailableError("down"))).restate(SAMUDA, CONTEXT, "en")

    assert not restated.used and "could not be reached" in restated.note


def test_no_article_no_restatement():

    client = StubClient(ANSWER)

    assert not ClaimRestater(client).restate(SAMUDA, None, "en").used
    assert client.prompts == []


# ----------------------------------------------------------------------
# What the later stages search
# ----------------------------------------------------------------------


def test_the_working_claim_asks_for_what_is_checked_not_who_said_it():

    working = working_claim(SAMUDA, validate(ANSWER, SAMUDA, CONTEXT, "en"))

    assert working.text == CHECKABLE
    assert working.entities == {"LOC": ["Jamaica"]}
    assert working.facts.figures == ["30"]


def test_a_name_the_restatement_put_back_becomes_an_anchor():

    answer = {**ANSWER, "checkable": "Matthew Samuda said Jamaica spent 30 years among the top three murder rates."}

    working = working_claim(SAMUDA, validate(answer, SAMUDA, CONTEXT, "en"))

    assert "Matthew Samuda" in working.entities.get("RESTATED", [])


def test_a_refused_restatement_leaves_the_claim_as_it_was():

    refused = validate(None, SAMUDA, CONTEXT, "en")

    assert working_claim(SAMUDA, refused) is SAMUDA


# ----------------------------------------------------------------------
# In the pipeline
# ----------------------------------------------------------------------


@pytest.mark.usefixtures("list_verifier")
def test_the_pipeline_searches_the_restatement_and_reports_the_sentence(repository):

    article = create_article(claims=[SAMUDA], title=CONTEXT.title, body=CONTEXT.lead)
    evidence = [create_evidence()]

    retriever = FakeEvidenceRetriever({CHECKABLE: evidence})

    checker = FactChecker(
        repository,
        claim_selector=ClaimSelector(embeddings=FakeEmbeddingService(vectors={SAMUDA.text: [1.0] + [0.0] * 7})),
        evidence_retriever=retriever,
        ranker=FakeRanker(),
        verifier=FakeVerifier({
            CHECKABLE: LLMVerificationResult(verdict=Verdict.TRUE, confidence=0.9, explanation="Yes.", cited_evidence=[0]),
        }),
        confidence_scorer=ConfidenceScorer(),
        restater=ClaimRestater(StubClient(ANSWER)),
    )

    events = []
    report = checker.run(
        article,
        on_phase=lambda phase, data: events.append((phase, data)),
        thresholds=PipelineThresholds(claim_restatement="standalone"),
    )

    # Searched as the checkable statement...
    assert retriever.calls[0][0].text == CHECKABLE

    # ...reported as the sentence, with what it was checked as beside it.
    [check] = report.claim_checks
    assert check.claim == SAMUDA.text
    assert check.restatement.checkable == CHECKABLE
    assert check.verdict == Verdict.TRUE

    restated = dict(events)["claim_restated"]
    assert restated["claim"] == SAMUDA.text and restated["restatement"]["kind"] == "attributed"


@pytest.mark.usefixtures("list_verifier")
def test_off_by_default_nothing_is_restated(repository):

    client = StubClient(ANSWER)
    article = create_article(claims=[SAMUDA], title=CONTEXT.title, body=CONTEXT.lead)

    checker = FactChecker(
        repository,
        claim_selector=ClaimSelector(embeddings=FakeEmbeddingService(vectors={SAMUDA.text: [1.0] + [0.0] * 7})),
        evidence_retriever=FakeEvidenceRetriever({SAMUDA.text: []}),
        ranker=FakeRanker(),
        verifier=FakeVerifier({}),
        confidence_scorer=ConfidenceScorer(),
        restater=ClaimRestater(client),
    )

    report = checker.run(article, thresholds=PipelineThresholds())

    assert client.prompts == [] and report.claim_checks[0].restatement is None


def test_a_capitalised_opening_is_not_taken_for_a_name():

    answer = {**ANSWER, "checkable": "Since October Jamaica spent 30 years among the top three murder rates."}

    working = working_claim(SAMUDA, validate(answer, SAMUDA, CONTEXT, "en"))

    assert "RESTATED" not in working.entities


# ----------------------------------------------------------------------
# What the 3B actually answered on 2026-11-03
# ----------------------------------------------------------------------


def test_a_topic_that_drops_the_figure_falls_back_to_the_standalone_sentence():

    answer = {**ANSWER, "checkable": "Jamaica's ranking in the most murderous countries on the planet"}

    restated = validate(answer, SAMUDA, CONTEXT, "en")

    assert restated.used and restated.checkable == ANSWER["standalone"]
    assert "dropped 30" in restated.note


def test_a_question_is_not_a_statement():

    answer = {
        **ANSWER,
        "checkable": "Did Jamaica spend 30 years among the three most murderous countries?",
        "standalone": "Did Samuda say that?",
    }

    restated = validate(answer, SAMUDA, CONTEXT, "en")

    assert not restated.used and "question" in restated.note


def test_a_sentence_with_a_figure_is_not_taken_for_an_opinion():

    restated = validate({**ANSWER, "kind": "opinion"}, SAMUDA, CONTEXT, "en")

    assert restated.used and restated.kind == "attributed" and restated.checkable == CHECKABLE


def test_an_opinion_without_a_figure_is_still_one():

    claim = Claim(text="Samuda argued the beaches should stay open to the hotels.", entities={}, confidence=0.8)

    restated = validate({**ANSWER, "kind": "opinion", "checkable": claim.text}, claim, CONTEXT, "en")

    assert not restated.used and restated.kind == "opinion"
