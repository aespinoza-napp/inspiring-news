"""
`query_plan: questions`: the questions a claim is searched by, held to the
claim without a model, one query each, and the answers their queries found.
"""

import dataclasses

import pytest

from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim, ClaimFacts
from src.models.fact_checker.evidence import EvidenceStance
from src.models.fact_checker.fact_check import Verdict
from src.models.fact_checker.questions import NO_ANSWER
from src.services.fact_checker.claim_selector import ArticleContext, ClaimSelector
from src.services.fact_checker.fact_checker import FactChecker
from src.services.fact_checker.questions import QuestionPlanner, answered, validate
from src.services.fact_checker.retrieval.checkable import carries, checkable_point
from src.services.fact_checker.retrieval.query_builder import QueryKind, plan_checkable, plan_queries
from src.services.fact_checker.verification.confidence_scorer import ConfidenceScorer
from src.services.fact_checker.verification.llm_verification import LLMVerificationResult
from src.services.llms import LLMUnavailableError

from tests.factories import create_article, create_evidence
from tests.services.fact_checker.fakes import FakeEmbeddingService, FakeEvidenceRetriever, FakeRanker, FakeVerifier

DENGUE = Claim(
    text="Florida has reported 212 travel-related dengue cases so far in 2026.",
    entities={"LOC": ["Florida"]},
    confidence=0.8,
    facts=ClaimFacts(figures=["212"], dates=["2026"]),
)

GOOD = "How many travel-related dengue cases has Florida reported in 2026?"


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


def point():
    return checkable_point(DENGUE, None, "en", "finding_closing", "counted")


# ----------------------------------------------------------------------
# Held to the claim
# ----------------------------------------------------------------------

def test_a_question_with_the_subject_and_a_detail_is_kept():

    plan = validate({"questions": [GOOD]}, DENGUE, point(), "en")

    [question] = plan.questions
    assert plan.used and question.kept
    assert question.detail == "2026" or question.detail == "Florida"
    assert question.tag == "question-1"
    assert '"212"' not in question.query and "Florida" in question.query


@pytest.mark.parametrize("text, reason", [
    ("Has Florida reported 2120 dengue cases in 2026?", "states 2120"),
    ("How many travel-related dengue cases were reported in 2026?", "subject"),
    ("Is the dengue situation in Florida worrying?", None),
])
def test_a_question_the_claim_does_not_support_is_refused(text, reason):

    plan = validate({"questions": [text]}, DENGUE, point(), "en")
    [question] = plan.questions

    if reason is None:
        # It names Florida, which is the subject and a decisive detail too.
        assert question.kept
    else:
        assert not question.kept and reason in question.reason
        assert not plan.used and "checkable plan" in plan.note


def test_no_more_than_three_and_no_repeats():

    questions = [
        GOOD,
        "How many travel-related dengue cases has Florida reported so far in 2026?",
        "Did Florida report 212 dengue cases in 2026?",
        "Which agency counts dengue cases in Florida?",
        "Which hospital in Florida treated the dengue cases?",
    ]

    plan = validate({"questions": questions}, DENGUE, point(), "en")

    assert [q.kept for q in plan.questions] == [True, False, True, True, False]
    assert plan.questions[1].reason == "repeats a kept question"
    assert plan.questions[4].reason == "past the first 3"
    assert [q.tag for q in plan.kept] == ["question-1", "question-2", "question-3"]


@pytest.mark.parametrize("answer", [None, {}, {"questions": "one"}, {"questions": []}])
def test_no_usable_answer_is_the_checkable_plan(answer):

    assert not validate(answer, DENGUE, point(), "en").used


def test_a_model_that_is_down_never_fails_the_claim():

    plan = QuestionPlanner(StubClient(raises=LLMUnavailableError("down"))).plan(DENGUE, None, "en")

    assert not plan.used and "could not be reached" in plan.note


def test_the_model_sees_the_claim_and_its_details_and_nothing_else():

    client = StubClient({"questions": [GOOD]})
    context = ArticleContext(title="Dengue in Florida", lead="Officials said...")

    QuestionPlanner(client).plan(DENGUE, context, "en")

    [prompt] = client.prompts
    assert DENGUE.text in prompt and "212" in prompt
    assert "Officials said" not in prompt


def test_carries_means_every_word_of_it():

    assert carries("What did Florida Health report?", "Florida Health")
    assert not carries("What did Florida report?", "Florida Health")
    assert not carries("Were there 2120 cases?", "212")


# ----------------------------------------------------------------------
# One query each
# ----------------------------------------------------------------------

def test_each_question_is_one_tagged_query():

    context = ArticleContext(search_questions=[GOOD, "Did Florida report 212 dengue cases in 2026?"])

    plan = plan_queries(DENGUE, context, "en", style="questions", terms_order="finding_closing", figures_style="counted")

    # The checkable plan's anchor first, for the pool; then each question.
    assert [query.kind for query in plan] == [QueryKind.ANCHOR, QueryKind.QUESTION, QueryKind.QUESTION]
    assert [query.label for query in plan] == ["anchor", "question-1", "question-2"]
    assert '"212"' in plan[2].text


def test_query_kinds_never_drop_a_question():

    context = ArticleContext(search_questions=[GOOD])

    plan = plan_queries(DENGUE, context, "en", kinds=("proposition",), style="questions")

    assert [query.kind for query in plan] == [QueryKind.QUESTION]


def test_no_question_kept_plans_as_checkable():

    planned = plan_queries(DENGUE, ArticleContext(), "en", style="questions", terms_order="finding_closing", figures_style="counted")

    assert planned == [q for q in plan_checkable(DENGUE, ArticleContext(), "en", "finding_closing", "counted") if q.text]


# ----------------------------------------------------------------------
# Answers
# ----------------------------------------------------------------------

def test_the_answer_is_the_first_judged_source_its_query_found():

    plan = validate({"questions": [GOOD, "Did Florida report 212 dengue cases in 2026?"]}, DENGUE, point(), "en")

    evidence = [
        # Silent: on the subject, says nothing on the point - answers nothing.
        create_evidence(url="https://s.example/0", snippet="Social authentication.").model_copy(
            update={"found_by": ["question-1", "question-2"], "stance": EvidenceStance.SILENT}
        ),
        create_evidence(url="https://a.example/1", snippet="Florida counted 180 cases.").model_copy(
            update={"found_by": ["question-2"], "stance": EvidenceStance.CONTRADICTS}
        ),
        create_evidence(url="https://b.example/2", snippet="Week 37: 212 travel-related cases.").model_copy(
            update={"found_by": ["question-1", "question-2"], "quote": "212 travel-related cases", "stance": EvidenceStance.SUPPORTS}
        ),
    ]

    first, second = answered(plan, evidence).kept

    assert first.answer == "212 travel-related cases" and first.answer_url == "https://b.example/2"
    assert second.answer == "Florida counted 180 cases." and second.answer_url == "https://a.example/1"

    nothing = answered(plan, [])
    assert {q.answer for q in nothing.kept} == {NO_ANSWER}


# ----------------------------------------------------------------------
# In the pipeline
# ----------------------------------------------------------------------

def checker(repository, client, retriever):

    return FactChecker(
        repository,
        claim_selector=ClaimSelector(embeddings=FakeEmbeddingService(vectors={DENGUE.text: [1.0] + [0.0] * 7})),
        evidence_retriever=retriever,
        ranker=FakeRanker(),
        verifier=FakeVerifier({
            DENGUE.text: LLMVerificationResult(verdict=Verdict.TRUE, confidence=0.9, explanation="Yes.", cited_evidence=[0]),
        }),
        confidence_scorer=ConfidenceScorer(),
        question_planner=QuestionPlanner(client),
    )


def test_the_pipeline_searches_by_the_questions_and_keeps_their_answers(repository):

    evidence = [create_evidence(snippet="212 travel-related cases in 2026.").model_copy(
        update={"found_by": ["question-1"], "stance": EvidenceStance.SUPPORTS}
    )]
    retriever = FakeEvidenceRetriever({DENGUE.text: evidence})

    events = []
    report = checker(repository, StubClient({"questions": [GOOD]}), retriever).run(
        create_article(claims=[DENGUE]),
        on_phase=lambda phase, data: events.append((phase, data)),
        thresholds=PipelineThresholds(query_plan="questions"),
    )

    # The questions reach the plan through the claim's own context.
    context = retriever.calls[0][2]
    assert context.search_questions == [GOOD]

    [check] = report.claim_checks
    [question] = check.question_plan.kept
    assert question.answer == "212 travel-related cases in 2026."

    phases = [phase for phase, _ in events]
    assert phases.index("planning_questions") < phases.index("questions_planned") < phases.index("retrieving_evidence")


@pytest.mark.usefixtures("list_verifier")
def test_no_question_is_asked_under_another_plan(repository):

    client = StubClient({"questions": [GOOD]})

    report = checker(repository, client, FakeEvidenceRetriever({DENGUE.text: []})).run(
        create_article(claims=[DENGUE]), thresholds=PipelineThresholds(query_plan="checkable"),
    )

    assert client.prompts == [] and report.claim_checks[0].question_plan is None


def test_no_questions_under_a_deadline(repository):

    client = StubClient({"questions": [GOOD]})

    report = checker(repository, client, FakeEvidenceRetriever({DENGUE.text: []})).run(
        create_article(claims=[DENGUE]),
        thresholds=PipelineThresholds(query_plan="questions", claim_deadline_seconds=30),
    )

    assert client.prompts == []
    assert not report.claim_checks[0].question_plan.used


# ----------------------------------------------------------------------
# Names: what the first 10 AVeriTeC train claims taught (6 Nov)
# ----------------------------------------------------------------------

from src.services.fact_checker.retrieval.checkable import is_proper, names_in  # noqa: E402
from src.services.fact_checker.retrieval.query_builder import question_query  # noqa: E402

BIDEN = Claim(
    text="Presidential candidate Joe Biden fought for decades to cut social security in the US.",
    entities={"person": ["Joe Biden", "Presidential candidate"], "country": ["US"]},
    confidence=1.0,
)

ZINKE = Claim(
    text="US Interior Secretary Ryan Zinke ordered a special flag to be raised whenever he entered the building.",
    entities={"country": ["US"], "person": ["Ryan Zinke"]},
    confidence=1.0,
)


@pytest.mark.parametrize("value, proper", [
    ("Joe Biden", True), ("UNESCO", True), ("Bank of England", True), ("Benigno Aquino III", True),
    ("Presidential candidate", False), ("mentally ill", False), ("hot milk", False), ("November 1st 2019", False),
])
def test_a_name_is_capitalised_word_by_word(value, proper):

    assert is_proper(value) is proper


def test_a_name_is_named_by_its_core_not_its_title():

    assert names_in("What flag did Ryan Zinke order?", "US Interior Secretary Ryan Zinke")
    assert not names_in("What flag did the Secretary order?", "US Interior Secretary Ryan Zinke")
    assert names_in("What did Aquino's government do?", "Benigno Aquino III")
    assert not names_in("Is it in the USA?", "US")


def test_a_question_about_a_presidential_candidate_is_not_about_biden():

    point = checkable_point(BIDEN, None, "en", "finding_closing", "counted")

    plan = validate({"questions": [
        "What document or study says that a Presidential candidate has fought to cut social security?",
        "Did Joe Biden fight for decades to cut social security in the US?",
    ]}, BIDEN, point, "en")

    first, second = plan.questions
    assert not first.kept and first.reason == "does not name the claim's subject"
    assert second.kept


def test_the_query_names_each_name_once_and_no_question_words():

    point = checkable_point(ZINKE, None, "en", "finding_closing", "counted")

    query = question_query("What was the special flag that Ryan Zinke ordered to be raised?", ZINKE, point, "en")

    assert query.count("Zinke") == 1
    assert "What" not in query.split()
    assert "flag" in query


def test_the_claims_first_name_leads_every_query():

    russia = Claim(
        text='Russian Authorities are not closing off the Russian internet using the "Sovereign Internet law".',
        entities={"organization": ["Russian Authorities"]},
        confidence=1.0,
    )
    point = checkable_point(russia, None, "en", "finding_closing", "counted")

    query = question_query("When did the Sovereign Internet law come into effect?", russia, point, "en")

    assert query.startswith("Russian Authorities")


def test_the_name_is_searched_as_the_question_writes_it():

    point = checkable_point(ZINKE, None, "en", "finding_closing", "counted")

    query = question_query("What was the special flag that Ryan Zinke ordered to be raised?", ZINKE, point, "en")

    assert "Ryan Zinke" in query and "Secretary" not in query
