from src.config.settings import settings
from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim
from src.models.fact_checker.evidence import Evidence
from src.models.fact_checker.fact_check import FactCheck, Verdict
from src.services.fact_checker.verification.llm_verification import LLMVerificationResult


class ConfidenceScorer:

    # MIN_EVIDENCE now comes from the run's thresholds, not a class
    # attribute frozen at import time. The weights stay environment-only:
    # they must sum to 1.0, and letting a request set one member of the
    # pair alone would silently de-normalise the score.
    LLM_WEIGHT = settings.CONFIDENCE_LLM_WEIGHT
    EVIDENCE_WEIGHT = settings.CONFIDENCE_EVIDENCE_WEIGHT

    def score(
        self,
        claim: Claim,
        evidence: list[Evidence],
        llm_result: LLMVerificationResult,
        thresholds: PipelineThresholds | None = None,
    ) -> FactCheck:

        thresholds = thresholds or PipelineThresholds()

        # Hard rule, not a weight: no evidence means we cannot verify the
        # claim at all, regardless of what the LLM says.
        if len(evidence) < thresholds.min_evidence_for_verdict:
            return FactCheck(
                verdict=Verdict.UNVERIFIED,
                explanation="No evidence could be retrieved for this claim; verdict forced to UNVERIFIED.",
                confidence=0.0,
                claim=claim.text,
                evidence=[],
                cited_evidence_indices=[],
                evidence_count=0,
            )

        confidence = max(0.0, min(
            llm_result.confidence * self.LLM_WEIGHT
            + self._evidence_quality(
                evidence,
                llm_result.cited_evidence,
                thresholds.max_evidence_per_claim,
            ) * self.EVIDENCE_WEIGHT,
            1.0,
        ))

        verdict = llm_result.verdict

        # A definitive verdict with zero citations, despite evidence being
        # available, is an ungrounded assertion - don't trust it.
        if verdict in (Verdict.TRUE, Verdict.FALSE, Verdict.MISLEADING) and not llm_result.cited_evidence:
            verdict = Verdict.UNVERIFIED
            confidence = min(confidence, 0.4)

        return FactCheck(
            verdict=verdict,
            explanation=llm_result.explanation,
            confidence=confidence,
            claim=claim.text,
            evidence=evidence,
            cited_evidence_indices=llm_result.cited_evidence,
            evidence_count=len(evidence),
        )

    def _evidence_quality(
        self,
        evidence: list[Evidence],
        cited: list[int],
        max_evidence: int,
    ) -> float:

        if not evidence:
            return 0.0

        avg_relevance = sum(item.relevance_score or 0.0 for item in evidence) / len(evidence)
        citation_ratio = len(cited) / len(evidence)

        # max_evidence is the run's threshold, not settings.*: this used to
        # read the environment default, so a run overriding
        # max_evidence_per_claim retrieved and ranked the right number of
        # items and then scored their quantity against a cap it never
        # used - 2/5 = 0.4 instead of 1.0, silently depressing the
        # confidence of every claim in that run.
        quantity_factor = min(len(evidence) / max_evidence, 1.0)

        return avg_relevance * 0.5 + citation_ratio * 0.3 + quantity_factor * 0.2
