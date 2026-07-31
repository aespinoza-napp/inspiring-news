from src.models.fact_checker.fact_check import Verdict
from src.services.fact_checker.claim_selector import ClaimSelector
from src.services.fact_checker.fact_checker import FactChecker
from src.services.fact_checker.verification.confidence_scorer import ConfidenceScorer
from src.services.fact_checker.verification.llm_verification import LLMVerificationResult

from tests.factories import create_article, create_claim, create_evidence
from tests.fact_checker.fakes import (
    FakeEmbeddingService,
    FakeEvidenceRetriever,
    FakeRanker,
    FakeVerifier,
)


def test_run_short_circuits_when_validation_fails(repository):

    article = create_article(topics=[])  # fails topic validation

    checker = FactChecker(repository)

    report = checker.run(article)

    assert report.validation_passed is False
    assert "topic_not_relevant" in report.skipped_reason
    assert report.claims_selected == 0
    assert report.claim_checks == []


def test_run_produces_worst_case_wins_overall_verdict(repository):

    claim_false = create_claim(text="Claim that turns out false.", confidence=0.9)
    claim_true = create_claim(text="Claim that turns out true.", confidence=0.8)

    article = create_article(claims=[claim_false, claim_true])

    embeddings = FakeEmbeddingService(vectors={
        claim_false.text: [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        claim_true.text: [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    })

    evidence_false = [create_evidence(url="https://a.com", relevance_score=0.9)]
    evidence_true = [create_evidence(url="https://b.com", relevance_score=0.9)]

    checker = FactChecker(
        repository,
        claim_selector=ClaimSelector(embeddings=embeddings),
        evidence_retriever=FakeEvidenceRetriever({
            claim_false.text: evidence_false,
            claim_true.text: evidence_true,
        }),
        ranker=FakeRanker(),
        verifier=FakeVerifier({
            claim_false.text: LLMVerificationResult(
                verdict=Verdict.FALSE,
                confidence=0.9,
                explanation="Contradicted by evidence.",
                cited_evidence=[0],
            ),
            claim_true.text: LLMVerificationResult(
                verdict=Verdict.TRUE,
                confidence=0.9,
                explanation="Confirmed by evidence.",
                cited_evidence=[0],
            ),
        }),
        confidence_scorer=ConfidenceScorer(),
    )

    report = checker.run(article)

    assert report.validation_passed is True
    assert report.claims_total == 2
    assert report.claims_selected == 2
    assert len(report.claim_checks) == 2

    verdicts = {check.claim: check.verdict for check in report.claim_checks}
    assert verdicts[claim_false.text] == Verdict.FALSE
    assert verdicts[claim_true.text] == Verdict.TRUE

    # One false claim should dominate the article-level verdict.
    assert report.overall_verdict == Verdict.FALSE
    assert 0.0 < report.overall_confidence <= 1.0


def test_run_with_no_claims_returns_unverified_overall(repository):

    article = create_article(claims=[])

    checker = FactChecker(
        repository,
        claim_selector=ClaimSelector(embeddings=FakeEmbeddingService()),
        evidence_retriever=FakeEvidenceRetriever({}),
        ranker=FakeRanker(),
        verifier=FakeVerifier({}),
        confidence_scorer=ConfidenceScorer(),
    )

    report = checker.run(article)

    assert report.validation_passed is True
    assert report.claims_selected == 0
    assert report.overall_verdict == Verdict.UNVERIFIED
    assert report.overall_confidence == 0.0


def test_run_reports_phases_when_validation_fails(repository):

    article = create_article(topics=[])

    checker = FactChecker(repository)

    events = []

    checker.run(article, on_phase=lambda phase, data: events.append((phase, data)))

    phases = [phase for phase, _ in events]
    assert phases == ["validating", "validated", "skipped"]

    validated_data = dict(events[1][1])
    assert validated_data["passed"] is False


def test_run_reports_a_phase_per_claim_and_final_summary(repository):

    claim = create_claim(text="A checkable claim.", confidence=0.9)

    article = create_article(claims=[claim])

    embeddings = FakeEmbeddingService(vectors={
        claim.text: [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    })

    checker = FactChecker(
        repository,
        claim_selector=ClaimSelector(embeddings=embeddings),
        evidence_retriever=FakeEvidenceRetriever({
            claim.text: [create_evidence(url="https://a.com", relevance_score=0.9)],
        }),
        ranker=FakeRanker(),
        verifier=FakeVerifier({
            claim.text: LLMVerificationResult(
                verdict=Verdict.TRUE,
                confidence=0.9,
                explanation="Confirmed.",
                cited_evidence=[0],
            ),
        }),
        confidence_scorer=ConfidenceScorer(),
    )

    events = []

    checker.run(article, on_phase=lambda phase, data: events.append((phase, data)))

    phases = [phase for phase, _ in events]
    assert phases == [
        "validating",
        "validated",
        "selecting_claims",
        "claims_selected",
        "claim_checked",
        "fact_check_done",
    ]

    claim_checked_data = dict(events[phases.index("claim_checked")][1])
    assert claim_checked_data["verdict"] == Verdict.TRUE
