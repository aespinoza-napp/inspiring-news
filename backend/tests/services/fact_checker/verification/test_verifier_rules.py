"""
What a verdict means (verifier_rules) and the verifier asked about one
source at a time (verifier_answer=per_source).

On 2026-10-22 the 3B answered FALSE to 21 of 45 true train claims, each
marking one source "contradicts", most of them explained as "the
evidence does not mention ...": data/evaluation/experiments/verifier/.
"""

from src.config.thresholds import PipelineThresholds
from src.models.fact_checker.evidence import EvidenceStance
from src.models.fact_checker.fact_check import Verdict
from src.services.fact_checker.verification import per_source
from src.services.fact_checker.verification.confidence_scorer import ConfidenceScorer
from src.services.fact_checker.verification.llm_verification import (
    COMPACT_STATED_SYSTEM_PROMPT,
    INVALID_OUTPUT_EXPLANATION,
    STATED_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    EvidenceAssessment,
    LLMVerificationResult,
    LLMVerifier,
    system_prompt,
)
from src.services.llms import LLMUnavailableError

from tests.factories import create_claim, create_evidence
from tests.services.fact_checker.fakes import FakeLLMClient

STATED = PipelineThresholds(verifier_rules="stated")
ORIGINAL = PipelineThresholds(verifier_rules="original")
PER_SOURCE = PipelineThresholds(verifier_answer="per_source")


def sources(*domains: str):

    return [
        create_evidence(
            url=f"https://{domain}/page-{index}",
            title=f"Page {index}",
            domain=domain,
            content=f"Page {index} says the agency confirmed the figure.",
            relevance_score=0.8,
        )
        for index, domain in enumerate(domains)
    ]


def answer(verdict: Verdict, cited: list[int], stances: dict[int, EvidenceStance]) -> LLMVerificationResult:

    return LLMVerificationResult(
        verdict=verdict,
        confidence=0.8,
        explanation="x",
        cited_evidence=cited,
        assessments=[EvidenceAssessment(index=index, stance=stance) for index, stance in stances.items()],
    )


# ----------------------------------------------------------------------
# The stated rules
# ----------------------------------------------------------------------


def test_each_answer_and_rule_set_has_its_prompt():

    assert system_prompt(ORIGINAL) == SYSTEM_PROMPT
    assert system_prompt(STATED) == STATED_SYSTEM_PROMPT
    assert system_prompt(PipelineThresholds(verifier_answer="compact", verifier_rules="stated")) == COMPACT_STATED_SYSTEM_PROMPT
    assert system_prompt(PER_SOURCE) == per_source.PER_SOURCE_SYSTEM_PROMPT

    # What the rules exist for, said to the model in so many words.
    assert '"silent"' in STATED_SYSTEM_PROMPT and "never makes a claim FALSE" in STATED_SYSTEM_PROMPT
    assert "silent" not in SYSTEM_PROMPT


def test_the_stated_prompt_is_the_one_sent():

    client = FakeLLMClient(responses={"verdict": "UNVERIFIED", "confidence": 0.1, "explanation": "x"})

    LLMVerifier(client=client).verify(create_claim(), sources("a.org"), thresholds=STATED)

    assert client.calls[0][0] == STATED_SYSTEM_PROMPT


def test_a_false_resting_on_silent_sources_is_unverified_under_the_stated_rules_only():

    evidence = sources("a.org", "b.org")
    said = answer(Verdict.FALSE, [0, 1], {0: EvidenceStance.SILENT, 1: EvidenceStance.SILENT})

    assert ConfidenceScorer().score(create_claim(), evidence, said, STATED).verdict == Verdict.UNVERIFIED
    # A source silent on the claim grounds no verdict under either rule set.
    assert ConfidenceScorer().score(create_claim(), evidence, said, ORIGINAL).verdict == Verdict.UNVERIFIED


def test_a_false_needs_a_cited_source_that_contradicts():

    evidence = sources("a.org", "b.org")

    # The 3B's own shape: FALSE, both cited, neither said to contradict.
    said = answer(Verdict.FALSE, [0, 1], {0: EvidenceStance.SUPPORTS})

    assert ConfidenceScorer().score(create_claim(), evidence, said, STATED).verdict == Verdict.UNVERIFIED
    assert ConfidenceScorer().score(create_claim(), evidence, said, ORIGINAL).verdict == Verdict.FALSE

    contradicted = answer(Verdict.FALSE, [1], {0: EvidenceStance.SILENT, 1: EvidenceStance.CONTRADICTS})

    assert ConfidenceScorer().score(create_claim(), evidence, contradicted, STATED).verdict == Verdict.FALSE


def test_a_true_needs_a_cited_source_that_supports():

    evidence = sources("a.org", "b.org")

    unsupported = answer(Verdict.TRUE, [0], {})
    supported = answer(Verdict.TRUE, [0], {0: EvidenceStance.SUPPORTS})

    assert ConfidenceScorer().score(create_claim(), evidence, unsupported, STATED).verdict == Verdict.UNVERIFIED
    assert ConfidenceScorer().score(create_claim(), evidence, supported, STATED).verdict == Verdict.TRUE


# ----------------------------------------------------------------------
# One source at a time
# ----------------------------------------------------------------------


def stanced(*stances: str | None) -> list[per_source.SourceAnswer]:

    return [
        per_source.SourceAnswer(index=index, stance=EvidenceStance(stance) if stance else None)
        for index, stance in enumerate(stances)
    ]


def test_the_verdict_follows_from_the_stances():

    evidence = sources("a.org", "b.org", "c.org", "d.org")

    assert per_source.verdict_from(stanced("supports", "silent", "silent", "unrelated"), evidence)[0] == Verdict.TRUE
    assert per_source.verdict_from(stanced("contradicts", "silent", None, "silent"), evidence)[0] == Verdict.FALSE
    assert per_source.verdict_from(stanced("silent", "silent", "unrelated", None), evidence) == (Verdict.UNVERIFIED, 0.0, [])

    # Disagreement: the side with more outlets; a tie is TRUE, which the
    # scorer makes PARTIALLY_TRUE for the contradicting source.
    assert per_source.verdict_from(stanced("supports", "contradicts", "contradicts", "silent"), evidence)[0] == Verdict.FALSE
    assert per_source.verdict_from(stanced("supports", "contradicts", "silent", "silent"), evidence)[:1] == (Verdict.TRUE,)


def test_two_pages_of_one_outlet_are_one_voice():

    evidence = sources("a.org", "b.org", "b.org", "c.org")

    verdict, _, cited = per_source.verdict_from(stanced("supports", "contradicts", "contradicts", "silent"), evidence)

    # One outlet each way: a tie, not two against one.
    assert verdict == Verdict.TRUE
    assert cited == [0, 1, 2]


def test_more_agreeing_outlets_is_more_confidence():

    evidence = sources("a.org", "b.org", "c.org", "d.org")

    one = per_source.verdict_from(stanced("supports", "silent", "silent", "silent"), evidence)[1]
    all_four = per_source.verdict_from(stanced("supports", "supports", "supports", "supports"), evidence)[1]

    assert 0.5 < one < all_four == 1.0


def test_each_source_is_asked_alone_and_the_verdict_comes_from_the_answers():

    evidence = sources("a.org", "b.org", "c.org")

    client = FakeLLMClient(responses=[
        {"stance": "silent", "quote": ""},
        {"stance": "contradicts", "quote": "Page 1 says the agency confirmed the figure."},
        {"stance": "unrelated", "quote": ""},
    ])

    result = LLMVerifier(client=client).verify(create_claim(), evidence, thresholds=PER_SOURCE, language="en")

    assert len(client.calls) == 3
    assert all(system == per_source.PER_SOURCE_SYSTEM_PROMPT for system, _ in client.calls)

    # Each prompt carries its own source and no other.
    for index, (_, user) in enumerate(client.calls):
        assert f"Page {index}" in user
        assert all(f"Page {other}" not in user for other in range(3) if other != index)

    assert result.verdict == Verdict.FALSE
    assert result.cited_evidence == [1]
    assert [(a.index, a.stance) for a in result.assessments] == [
        (0, EvidenceStance.SILENT), (1, EvidenceStance.CONTRADICTS), (2, EvidenceStance.UNRELATED),
    ]
    # The quote was in the source, so it is kept and shown.
    assert result.assessments[1].quote == "Page 1 says the agency confirmed the figure."
    assert "b.org states otherwise" in result.explanation


def test_an_invented_quote_is_dropped_but_the_stance_stands():

    client = FakeLLMClient(responses=[{"stance": "supports", "quote": "A sentence no page contains anywhere."}])

    result = LLMVerifier(client=client).verify(create_claim(), sources("a.org"), thresholds=PER_SOURCE)

    assert result.verdict == Verdict.TRUE
    assert result.assessments[0].quote is None


def test_a_source_the_model_failed_on_has_no_stance_and_the_rest_still_count():

    client = FakeLLMClient(responses=[
        LLMUnavailableError("timed out"),
        {"stance": "supports", "quote": ""},
        "not a json object",
    ])

    result = LLMVerifier(client=client).verify(create_claim(), sources("a.org", "b.org", "c.org"), thresholds=PER_SOURCE)

    assert result.verdict == Verdict.TRUE
    assert not result.llm_unreachable
    assert [a.index for a in result.assessments] == [1]


def test_no_source_reached_is_not_checked_and_no_usable_answer_is_invalid_output():

    unreachable = LLMVerifier(client=FakeLLMClient(responses=LLMUnavailableError("down"))).verify(
        create_claim(), sources("a.org", "b.org"), thresholds=PER_SOURCE,
    )

    assert unreachable.llm_unreachable
    assert unreachable.verdict == Verdict.UNVERIFIED

    garbled = LLMVerifier(client=FakeLLMClient(responses={"stance": "maybe"})).verify(
        create_claim(), sources("a.org", "b.org"), thresholds=PER_SOURCE,
    )

    assert not garbled.llm_unreachable
    assert garbled.explanation == INVALID_OUTPUT_EXPLANATION


def test_the_claims_time_left_is_shared_by_its_sources():

    client = FakeLLMClient(responses={"stance": "silent", "quote": ""})

    LLMVerifier(client=client).verify(create_claim(), sources("a.org", "b.org"), thresholds=PER_SOURCE, timeout=30.0)

    first, second = client.timeouts

    assert 0 < second <= first <= 30.0


def test_a_source_with_no_time_left_is_not_asked():

    client = FakeLLMClient(responses={"stance": "supports", "quote": ""})

    result = LLMVerifier(client=client).verify(create_claim(), sources("a.org", "b.org"), thresholds=PER_SOURCE, timeout=0.5)

    assert client.calls == []
    assert result.llm_unreachable


def test_the_calls_are_summed_for_the_timing_panel():

    answers = [
        per_source.SourceAnswer(index=0, call={"model": "m", "wait": 0.0, "seconds": 2.5, "promptTokens": 300, "completionTokens": 20}),
        per_source.SourceAnswer(index=1, call={"model": "m", "wait": 1.0, "seconds": 3.0, "promptTokens": 280, "completionTokens": 25}),
        per_source.SourceAnswer(index=2),
    ]

    assert per_source.merged_call(answers) == {
        "model": "m", "wait": 1.0, "seconds": 5.5, "promptTokens": 580, "completionTokens": 45, "calls": 2,
    }


def test_the_explanation_is_in_the_claims_language():

    evidence = sources("a.org", "b.org")

    text = per_source.explanation(stanced("supports", "silent"), evidence, "es")

    assert text == "[0] a.org lo afirma; 1 no dicen nada al respecto."


# ----------------------------------------------------------------------
# What a reader is told
# ----------------------------------------------------------------------


def test_the_stage_note_says_why_the_stated_rules_took_a_false_back():

    from src.services.fact_checker.fact_checker import FactChecker
    from tests.services.fact_checker.fakes import FakeEvidenceRetriever, FakeRanker

    claim = create_claim()
    evidence = sources("a.org", "b.org")

    client = FakeLLMClient(responses={
        "verdict": "FALSE", "confidence": 0.8, "explanation": "The evidence does not mention 2024.",
        "cited_evidence": [0],
        "assessments": [{"index": 0, "stance": "silent", "quote": ""}, {"index": 1, "stance": "silent", "quote": ""}],
    })

    checker = FactChecker(
        None,
        evidence_retriever=FakeEvidenceRetriever({claim.text: evidence}),
        ranker=FakeRanker(),
        verifier=LLMVerifier(client=client),
        confidence_scorer=ConfidenceScorer(),
    )

    check = checker.check_claim(claim, thresholds=STATED.model_copy(update={"min_independent_domains": 1}))

    assert check.verdict == Verdict.UNVERIFIED
    assert check.raw_verdict == Verdict.FALSE
    assert check.stage_note == "LLM verdict FALSE recalibrated to UNVERIFIED: no source it cited states otherwise."
