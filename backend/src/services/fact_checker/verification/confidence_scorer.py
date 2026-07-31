from src.config.settings import settings
from src.models.claim import Claim
from src.models.evidence import Evidence
from src.models.fact_check import FactCheck, Verdict
from src.services.fact_checker.verification.llm_verification import LLMVerificationResult


class ConfidenceScorer:

    MIN_EVIDENCE = settings.MIN_EVIDENCE_FOR_VERDICT

    LLM_WEIGHT = 0.7
    EVIDENCE_WEIGHT = 0.3

    def score(
        self,
        claim: Claim,
        evidence: list[Evidence],
        llm_result: LLMVerificationResult,
    ) -> FactCheck:

        # Hard rule, not a weight: no evidence means we cannot verify the
        # claim at all, regardless of what the LLM says.
        if len(evidence) < self.MIN_EVIDENCE:
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
            + self._evidence_quality(evidence, llm_result.cited_evidence) * self.EVIDENCE_WEIGHT,
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

    def _evidence_quality(self, evidence: list[Evidence], cited: list[int]) -> float:

        if not evidence:
            return 0.0

        avg_relevance = sum(item.relevance_score or 0.0 for item in evidence) / len(evidence)
        citation_ratio = len(cited) / len(evidence)
        quantity_factor = min(len(evidence) / settings.MAX_EVIDENCE_PER_CLAIM, 1.0)

        return avg_relevance * 0.5 + citation_ratio * 0.3 + quantity_factor * 0.2
