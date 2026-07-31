from src.models.core.claim import Claim
from src.models.core.enriched_article import EnrichedArticle
from src.models.fact_checker.fact_check import FactCheck, Verdict
from src.models.fact_checker.fact_check_report import FactCheckReport
from src.repositories.vector_repository import VectorRepository
from src.services.fact_checker.claim_selector import ClaimSelector
from src.services.fact_checker.ranking.ranking_retrieval import EvidenceRanker
from src.services.fact_checker.retrieval.evidence_retriever import EvidenceRetriever
from src.services.fact_checker.validation_pipeline import (
    ValidationPipeline,
    ValidationPipelineResult,
)
from src.services.fact_checker.verification.confidence_scorer import ConfidenceScorer
from src.services.fact_checker.verification.llm_verification import LLMVerifier

_VERDICT_SEVERITY = {
    Verdict.TRUE: 0,
    Verdict.UNVERIFIED: 1,
    Verdict.MISLEADING: 2,
    Verdict.FALSE: 3,
}


class FactChecker:
    """
    Top-level orchestrator: validates an EnrichedArticle, and - only if
    validation passes - selects its most check-worthy claims and verifies
    each one against retrieved evidence, producing a FactCheckReport.
    """

    def __init__(
        self,
        repository: VectorRepository,
        validation_pipeline: ValidationPipeline | None = None,
        claim_selector: ClaimSelector | None = None,
        evidence_retriever: EvidenceRetriever | None = None,
        ranker: EvidenceRanker | None = None,
        verifier: LLMVerifier | None = None,
        confidence_scorer: ConfidenceScorer | None = None,
    ):
        self.validation_pipeline = validation_pipeline or ValidationPipeline(repository)
        self.claim_selector = claim_selector or ClaimSelector()
        self.evidence_retriever = evidence_retriever or EvidenceRetriever(repository)
        self.ranker = ranker or EvidenceRanker()
        self.verifier = verifier or LLMVerifier()
        self.confidence_scorer = confidence_scorer or ConfidenceScorer()

    def run(self, article: EnrichedArticle) -> FactCheckReport:

        validation = self.validation_pipeline.validate(article)

        if not validation.passed:
            return FactCheckReport(
                article_id=article.id,
                validation_passed=False,
                skipped_reason=self._reason(validation),
                claims_total=len(article.claims or []),
                claims_selected=0,
            )

        selected = self.claim_selector.select(article.claims or [])

        claim_checks = [self._check_claim(claim) for claim in selected]

        return FactCheckReport(
            article_id=article.id,
            validation_passed=True,
            claims_total=len(article.claims or []),
            claims_selected=len(selected),
            claim_checks=claim_checks,
            overall_verdict=self._aggregate_verdict(claim_checks),
            overall_confidence=self._aggregate_confidence(claim_checks),
        )

    def _check_claim(self, claim: Claim) -> FactCheck:

        evidence = self.evidence_retriever.retrieve(claim)
        ranked = self.ranker.rank(claim, evidence)
        llm_result = self.verifier.verify(claim, ranked)

        return self.confidence_scorer.score(claim, ranked, llm_result)

    @staticmethod
    def _aggregate_verdict(claim_checks: list[FactCheck]) -> Verdict:

        if not claim_checks:
            return Verdict.UNVERIFIED

        return max(
            (check.verdict for check in claim_checks),
            key=lambda verdict: _VERDICT_SEVERITY[verdict],
        )

    @staticmethod
    def _aggregate_confidence(claim_checks: list[FactCheck]) -> float:

        if not claim_checks:
            return 0.0

        return sum(check.confidence for check in claim_checks) / len(claim_checks)

    @staticmethod
    def _reason(validation: ValidationPipelineResult) -> str:

        reasons = []

        if not validation.topic_ok:
            reasons.append("topic_not_relevant")

        if not validation.positive_ok:
            reasons.append("not_positive_impact")

        if validation.duplicate:
            reasons.append("duplicate_article")

        return ",".join(reasons) or "validation_failed"
