from src.config.thresholds import PipelineThresholds
from src.models.fact_checker.evidence import EvidenceStance
from src.models.fact_checker.fact_check import Verdict
from src.services.fact_checker.verification.confidence_scorer import ConfidenceScorer
from src.services.fact_checker.verification.llm_verification import (
    EvidenceAssessment,
    LLMVerificationResult,
)

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

    # Two genuinely different outlets, as "confirmed by both sources"
    # implies. They used to be two copies of the same default URL, which
    # is one source cited twice - and is now capped as such.
    evidence = [
        create_evidence(relevance_score=0.9, url="https://a.example/x", domain="a.example"),
        create_evidence(relevance_score=0.8, url="https://b.example/y", domain="b.example"),
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


def test_contradicting_source_turns_a_true_verdict_partially_true():
    """
    The ordinary shape of a real verification: the central assertion
    holds, one source disagrees about a detail. Collapsing that into TRUE
    throws away the only part a reader needs to see.
    """

    evidence = [
        create_evidence(url="https://a.example/x", domain="a.example", relevance_score=0.9),
        create_evidence(url="https://b.example/y", domain="b.example", relevance_score=0.8),
    ]

    llm_result = LLMVerificationResult(
        verdict=Verdict.TRUE,
        confidence=0.9,
        explanation="Mostly confirmed.",
        cited_evidence=[0, 1],
        assessments=[
            EvidenceAssessment(index=0, stance=EvidenceStance.SUPPORTS, quote="the grid hit 50%"),
            EvidenceAssessment(index=1, stance=EvidenceStance.CONTRADICTS, quote="the figure was 45%"),
        ],
    )

    result = ConfidenceScorer().score(create_claim(), evidence, llm_result)

    assert result.verdict == Verdict.PARTIALLY_TRUE
    assert result.agreements == ["a.example: the grid hit 50%"]
    assert result.discrepancies == ["b.example: the figure was 45%"]


def test_a_single_outlet_repeated_is_not_corroboration():
    """
    Five syndications of one wire story are one source. Counting raw
    evidence items instead of distinct domains is what let that read as
    five independent confirmations.
    """

    evidence = [
        create_evidence(url="https://a.example/x", domain="a.example", relevance_score=0.9),
        create_evidence(url="https://a.example/y", domain="a.example", relevance_score=0.9),
    ]

    llm_result = LLMVerificationResult(
        verdict=Verdict.TRUE,
        confidence=0.95,
        explanation="Confirmed.",
        cited_evidence=[0, 1],
        assessments=[
            EvidenceAssessment(index=0, stance=EvidenceStance.SUPPORTS),
            EvidenceAssessment(index=1, stance=EvidenceStance.SUPPORTS),
        ],
    )

    result = ConfidenceScorer().score(
        create_claim(),
        evidence,
        llm_result,
        PipelineThresholds(min_independent_domains=2),
    )

    assert result.independent_domains == 1
    assert result.confidence <= 0.6
