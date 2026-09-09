from logging import getLogger
from typing import Callable, Optional

from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim
from src.models.core.enriched_article import EnrichedArticle
from src.models.fact_checker.evidence import Evidence, RejectedEvidence
from src.models.fact_checker.fact_check import FactCheck, Verdict
from src.models.fact_checker.fact_check_report import FactCheckReport
from src.models.fact_checker.pipeline_stage import PipelineStage
from src.repositories.vector_repository import VectorRepository
from src.services.fact_checker.claim_selector import ClaimSelector
from src.services.fact_checker.ranking.ranking_retrieval import EvidenceRanker
from src.services.fact_checker.retrieval.evidence_retriever import EvidenceRetriever
from src.services.fact_checker.validation_pipeline import (
    ValidationPipeline,
    ValidationPipelineResult,
)
from src.services.fact_checker.verification.confidence_scorer import ConfidenceScorer
from src.services.fact_checker.verification.llm_verification import (
    LLMVerificationResult,
    LLMVerifier,
)

logger = getLogger(__name__)

OnPhase = Callable[[str, dict], None]


def _noop(phase: str, data: dict) -> None:
    pass

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
        self.repository = repository
        self.validation_pipeline = validation_pipeline or ValidationPipeline(repository)
        self.claim_selector = claim_selector or ClaimSelector()
        self.evidence_retriever = evidence_retriever or EvidenceRetriever(repository)
        self.ranker = ranker or EvidenceRanker()
        self.verifier = verifier or LLMVerifier()
        self.confidence_scorer = confidence_scorer or ConfidenceScorer()

    def run(
        self,
        article: EnrichedArticle,
        on_phase: Optional[OnPhase] = None,
        thresholds: PipelineThresholds | None = None,
    ) -> FactCheckReport:

        report_phase = on_phase or _noop

        thresholds = thresholds or PipelineThresholds()

        report_phase("validating", {})

        validation = self.validation_pipeline.validate(article, thresholds)

        report_phase("validated", {
            "topicOk": validation.topic_ok,
            "positiveOk": validation.positive_ok,
            "duplicate": validation.duplicate,
            "passed": validation.passed,
            "impactScore": validation.impact_score,
            "impactReasons": validation.impact_reasons,
        })

        if not validation.passed:

            reason = self._reason(validation)

            report_phase("skipped", {"reason": reason})

            return FactCheckReport(
                article_id=article.id,
                validation_passed=False,
                skipped_reason=reason,
                topic_ok=validation.topic_ok,
                positive_ok=validation.positive_ok,
                impact_score=validation.impact_score,
                impact_reasons=validation.impact_reasons,
                duplicate=validation.duplicate,
                failed_stage=PipelineStage.ADMISSION_FILTER,
                claims_total=len(article.claims or []),
                claims_selected=0,
            )

        report_phase("selecting_claims", {})

        selection = self.claim_selector.select(article.claims or [], thresholds)
        selected = selection.selected

        report_phase("claims_selected", {"count": len(selected)})

        claim_checks = [
            self._check_claim(claim, report_phase, thresholds)
            for claim in selected
        ]

        # Persist the article now that its own claim-checks are done (not
        # before - EvidenceRetriever's internal-corpus lookup would
        # otherwise sometimes surface this very article as "evidence" for
        # its own claims). Nothing else in the app calls
        # VectorRepository.save() at all, so without this every duplicate
        # check and every internal-evidence lookup was permanently
        # querying an empty collection - confirmed live: DuplicateValidator
        # never flagged a duplicate even when re-validating the exact same
        # article object twice in a row.
        try:
            self.repository.save(article)
        except Exception:
            logger.warning("Failed to persist article %s to the vector store", article.id, exc_info=True)

        report = FactCheckReport(
            article_id=article.id,
            validation_passed=True,
            topic_ok=validation.topic_ok,
            positive_ok=validation.positive_ok,
            impact_score=validation.impact_score,
            impact_reasons=validation.impact_reasons,
            duplicate=validation.duplicate,
            claims_total=len(article.claims or []),
            claims_selected=len(selected),
            claim_checks=claim_checks,
            unselected_claims=selection.rejected,
            overall_verdict=self._aggregate_verdict(claim_checks),
            overall_confidence=self._aggregate_confidence(claim_checks),
        )

        report_phase("fact_check_done", {
            "overallVerdict": report.overall_verdict,
            "overallConfidence": report.overall_confidence,
        })

        return report

    def check_claim(
        self,
        claim: Claim,
        on_phase: Optional[OnPhase] = None,
        thresholds: PipelineThresholds | None = None,
    ) -> FactCheck:
        """
        Verify one claim on its own: retrieve evidence, rank it, ask the
        LLM, then recalibrate the confidence.

        Public because a single claim is a useful unit by itself, not
        only as a step inside an article run - POST /verify-claim calls
        exactly this, so the standalone checker and the pipeline cannot
        drift apart in what they consider verified.

        Note this skips the admission filter (topic/positivity/duplicate)
        and claim selection entirely: those judge an *article*, and a
        bare claim has neither.
        """

        return self._check_claim(
            claim,
            on_phase or _noop,
            thresholds or PipelineThresholds(),
        )

    def _check_claim(
        self,
        claim: Claim,
        report_phase: OnPhase,
        thresholds: PipelineThresholds,
    ) -> FactCheck:

        # The four sub-stages below are the slowest in the whole pipeline -
        # a live SearXNG search, scraping the top hits, and one LLM call -
        # and they used to emit nothing until `claim_checked` at the very
        # end. A five-claim article therefore showed the client four
        # updates spread over a minute of apparent silence. CLAUDE.md's
        # rule is per stage, not per method.

        report_phase("retrieving_evidence", {"claim": claim.text})

        retrieval = self.evidence_retriever.retrieve(claim, thresholds)

        report_phase("evidence_retrieved", {
            "claim": claim.text,
            "found": len(retrieval.kept),
            "rejected": len(retrieval.rejected),
        })

        ranking = self.ranker.rank(claim, retrieval.kept, thresholds)
        ranked = ranking.kept

        # Ranking is embedding arithmetic over a handful of items, fast
        # enough not to deserve its own pair of events - but the LLM call
        # after it is the single longest step, so it gets one.
        report_phase("verifying_claim", {
            "claim": claim.text,
            "evidence": len(ranked),
        })

        llm_result = self.verifier.verify(claim, ranked)

        check = self.confidence_scorer.score(claim, ranked, llm_result, thresholds)

        not_cited = [
            RejectedEvidence(
                url=item.url,
                title=item.title,
                origin=item.origin,
                stage=PipelineStage.LLM_VERIFICATION,
                reason="retrieved and ranked, but not cited by the LLM",
                score=item.relevance_score,
            )
            for index, item in enumerate(ranked)
            if index not in llm_result.cited_evidence
        ]

        reached_stage, stage_note = self._trace(
            ranked, llm_result, check, thresholds
        )

        check = check.model_copy(update={
            "rejected_sources": retrieval.rejected + ranking.rejected + not_cited,
            "reached_stage": reached_stage,
            "stage_note": stage_note,
            "raw_verdict": llm_result.verdict,
            "raw_confidence": llm_result.confidence,
        })

        report_phase("claim_checked", {
            "claim": check.claim,
            "verdict": check.verdict,
            "confidence": check.confidence,
            "explanation": check.explanation,
        })

        return check

    def _trace(
        self,
        ranked: list[Evidence],
        llm_result: LLMVerificationResult,
        check: FactCheck,
        thresholds: PipelineThresholds,
    ) -> tuple[PipelineStage, Optional[str]]:

        if len(ranked) < thresholds.min_evidence_for_verdict:
            return (
                PipelineStage.CONFIDENCE_RECALIBRATION,
                "No evidence could be retrieved for this claim; verdict forced to UNVERIFIED.",
            )

        if check.verdict != llm_result.verdict:
            return (
                PipelineStage.CONFIDENCE_RECALIBRATION,
                f"LLM verdict {llm_result.verdict.value} cited no evidence; "
                "downgraded to UNVERIFIED with a low confidence ceiling.",
            )

        return PipelineStage.AGGREGATION, None

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
