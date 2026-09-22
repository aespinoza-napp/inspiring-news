from src.models.fact_checker.fact_check import Verdict
from src.services.fact_checker.verification.llm_verification import LLMVerifier
from src.services.llms import LLMUnavailableError

from tests.factories import create_claim, create_evidence
from tests.services.fact_checker.fakes import FakeLLMClient


def test_verify_returns_normalized_result_on_valid_response():

    client = FakeLLMClient(responses={
        "verdict": "TRUE",
        "confidence": 0.85,
        "explanation": "Confirmed by evidence [0].",
        "cited_evidence": [0],
    })

    verifier = LLMVerifier(client=client)

    evidence = [create_evidence()]

    result = verifier.verify(create_claim(), evidence)

    assert result.verdict == Verdict.TRUE
    assert result.confidence == 0.85
    assert result.explanation == "Confirmed by evidence [0]."
    assert result.cited_evidence == [0]


def test_verify_defaults_to_unverified_on_invalid_verdict_string():

    client = FakeLLMClient(responses={
        "verdict": "MAYBE",
        "confidence": 0.9,
        "explanation": "unsure",
        "cited_evidence": [],
    })

    verifier = LLMVerifier(client=client)

    result = verifier.verify(create_claim(), [create_evidence()])

    assert result.verdict == Verdict.UNVERIFIED


def test_verify_clamps_out_of_range_confidence():

    client = FakeLLMClient(responses={
        "verdict": "FALSE",
        "confidence": 5.0,
        "explanation": "way too confident",
        "cited_evidence": [],
    })

    verifier = LLMVerifier(client=client)

    result = verifier.verify(create_claim(), [create_evidence()])

    assert result.confidence == 1.0


def test_verify_filters_out_of_range_cited_evidence_indices():

    evidence = [create_evidence(), create_evidence()]

    client = FakeLLMClient(responses={
        "verdict": "TRUE",
        "confidence": 0.7,
        "explanation": "ok",
        "cited_evidence": [0, 1, 5, -1],
    })

    verifier = LLMVerifier(client=client)

    result = verifier.verify(create_claim(), evidence)

    assert result.cited_evidence == [0, 1]


def test_verify_falls_back_to_unverified_when_client_returns_none():

    client = FakeLLMClient(responses=None)

    verifier = LLMVerifier(client=client)

    result = verifier.verify(create_claim(), [create_evidence()])

    assert result.verdict == Verdict.UNVERIFIED
    assert result.confidence == 0.0


def test_verify_marks_llm_unreachable_distinctly_from_a_real_unverified():
    """
    A dead socket and a model that found no support both surface as
    UNVERIFIED, but only one of them should set llm_unreachable - that
    flag is what lets a caller (or a Phase 4 benchmark) tell them apart.
    """

    client = FakeLLMClient(responses=LLMUnavailableError("connection refused"))

    verifier = LLMVerifier(client=client)

    result = verifier.verify(create_claim(), [create_evidence()])

    assert result.verdict == Verdict.UNVERIFIED
    assert result.llm_unreachable is True


def test_verify_does_not_mark_unreachable_for_an_ordinary_unverified():

    client = FakeLLMClient(responses=None)

    result = LLMVerifier(client=client).verify(create_claim(), [create_evidence()])

    assert result.verdict == Verdict.UNVERIFIED
    assert result.llm_unreachable is False


def test_verify_handles_missing_confidence_field():

    client = FakeLLMClient(responses={
        "verdict": "UNVERIFIED",
        "explanation": "no confidence given",
    })

    verifier = LLMVerifier(client=client)

    result = verifier.verify(create_claim(), [])

    assert result.confidence == 0.0


def test_verify_builds_prompt_with_no_evidence_marker():

    client = FakeLLMClient(responses={"verdict": "UNVERIFIED", "confidence": 0.0, "explanation": "n/a"})

    verifier = LLMVerifier(client=client)

    verifier.verify(create_claim(), [])

    _, user_prompt = client.calls[0]
    assert "(no evidence retrieved)" in user_prompt


# ----------------------------------------------------------------------
# Per-source assessments
# ----------------------------------------------------------------------


def test_a_quote_not_present_in_the_source_is_dropped():
    """
    A small local model will produce a plausible sentence and present it
    as a quotation. An invented quote is worse than no quote: it is the
    one part of this output a reader would take at face value without
    clicking through to check it.
    """

    evidence = [create_evidence(content="The grid ran on 50% renewables in 2024.")]

    client = FakeLLMClient(responses={
        "verdict": "TRUE",
        "confidence": 0.9,
        "explanation": "Confirmed.",
        "cited_evidence": [0],
        "assessments": [
            {
                "index": 0,
                "stance": "supports",
                "quote": "Officials hailed it as a historic milestone.",
            },
        ],
    })

    result = LLMVerifier(client=client).verify(create_claim(), evidence)

    assert result.assessments[0].stance.value == "supports"
    assert result.assessments[0].quote is None


def test_a_quote_present_in_the_source_is_kept():

    evidence = [create_evidence(content="The grid ran on 50% renewables in 2024.")]

    client = FakeLLMClient(responses={
        "verdict": "TRUE",
        "confidence": 0.9,
        "explanation": "Confirmed.",
        "cited_evidence": [0],
        "assessments": [
            {"index": 0, "stance": "supports", "quote": "ran on 50% renewables"},
        ],
    })

    result = LLMVerifier(client=client).verify(create_claim(), evidence)

    assert result.assessments[0].quote == "ran on 50% renewables"


def test_a_malformed_assessments_block_does_not_lose_the_verdict():
    """
    The per-source block is the most likely part of the response for a
    local model to get wrong. Losing the verdict that came back with it
    would make the whole response fail on the model's weakest output.
    """

    client = FakeLLMClient(responses={
        "verdict": "FALSE",
        "confidence": 0.8,
        "explanation": "Contradicted.",
        "cited_evidence": [0],
        "assessments": "not a list at all",
    })

    result = LLMVerifier(client=client).verify(
        create_claim(), [create_evidence()]
    )

    assert result.verdict == Verdict.FALSE
    assert result.confidence == 0.8
    assert result.assessments == []


def test_assessments_pointing_at_evidence_that_does_not_exist_are_discarded():

    client = FakeLLMClient(responses={
        "verdict": "TRUE",
        "confidence": 0.7,
        "explanation": "Confirmed.",
        "cited_evidence": [0],
        "assessments": [
            {"index": 0, "stance": "supports", "quote": ""},
            {"index": 99, "stance": "contradicts", "quote": ""},
            {"index": 0, "stance": "contradicts", "quote": ""},
        ],
    })

    result = LLMVerifier(client=client).verify(
        create_claim(), [create_evidence()]
    )

    # Out of range dropped, and the duplicate index does not get a
    # second, conflicting stance for the same source.
    assert [a.index for a in result.assessments] == [0]
    assert result.assessments[0].stance.value == "supports"
