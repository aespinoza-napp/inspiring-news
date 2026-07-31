from src.models.fact_checker.fact_check import Verdict
from src.services.fact_checker.verification.llm_verification import LLMVerifier

from tests.factories import create_claim, create_evidence
from tests.fact_checker.fakes import FakeLLMClient


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
