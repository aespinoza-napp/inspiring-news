from src.models.fact_check import Verdict
from src.services.fact_checker.verification.confidence_scorer import ConfidenceScorer
from src.services.fact_checker.verification.llm_verification import LLMVerificationResult

from tests.factories import create_claim, create_evidence


def test_zero_evidence_forces_unverified_even_if_llm_is_confident():

    llm_result = LLMVerificationResult(
        verdict=Verdict.TRUE,
        confidence=0.99,
        explanation="I am very sure this is true.",
        cited_evidence=[],
    )

    scorer = ConfidenceScorer()

    result = scorer.score(create_claim(), [], llm_result)

    assert result.verdict == Verdict.UNVERIFIED
    assert result.confidence == 0.0
    assert result.evidence_count == 0


def test_definitive_verdict_without_citations_is_downgraded():

    evidence = [create_evidence(relevance_score=0.9)]

    llm_result = LLMVerificationResult(
        verdict=Verdict.FALSE,
        confidence=0.9,
        explanation="This seems false.",
        cited_evidence=[],
    )

    scorer = ConfidenceScorer()

    result = scorer.score(create_claim(), evidence, llm_result)

    assert result.verdict == Verdict.UNVERIFIED
    assert result.confidence <= 0.4


def test_cited_verdict_with_evidence_is_kept_and_weighted():

    evidence = [
        create_evidence(relevance_score=0.9),
        create_evidence(relevance_score=0.8),
    ]

    llm_result = LLMVerificationResult(
        verdict=Verdict.TRUE,
        confidence=0.9,
        explanation="Confirmed by both sources.",
        cited_evidence=[0, 1],
    )

    scorer = ConfidenceScorer()

    result = scorer.score(create_claim(), evidence, llm_result)

    assert result.verdict == Verdict.TRUE
    assert result.claim == create_claim().text
    assert result.evidence_count == 2
    assert result.cited_evidence_indices == [0, 1]
    assert 0.0 < result.confidence <= 1.0
    # LLM confidence (0.9) weighted 0.7 plus a nonzero evidence-quality term
    # should land meaningfully above a bare pass-through of either input alone.
    assert result.confidence > 0.6


def test_unverified_llm_verdict_with_evidence_stays_unverified():

    evidence = [create_evidence(relevance_score=0.2)]

    llm_result = LLMVerificationResult(
        verdict=Verdict.UNVERIFIED,
        confidence=0.3,
        explanation="Evidence is inconclusive.",
        cited_evidence=[],
    )

    scorer = ConfidenceScorer()

    result = scorer.score(create_claim(), evidence, llm_result)

    assert result.verdict == Verdict.UNVERIFIED
