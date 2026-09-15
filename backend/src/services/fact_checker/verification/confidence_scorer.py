from src.config.settings import settings
from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim
from src.models.fact_checker.evidence import Evidence, EvidenceStance
from src.models.fact_checker.fact_check import FactCheck, Verdict
from src.services.fact_checker.verification.llm_verification import LLMVerificationResult

# Verdicts that assert something definite about the claim, as opposed to
# declining to judge it.
_DEFINITIVE = (Verdict.TRUE, Verdict.PARTIALLY_TRUE, Verdict.FALSE, Verdict.MISLEADING)


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

        annotated = self._annotate(evidence, llm_result)

        supporting = [
            item for item in annotated if item.stance == EvidenceStance.SUPPORTS
        ]
        contradicting = [
            item for item in annotated if item.stance == EvidenceStance.CONTRADICTS
        ]

        # No per-source stances at all means the model did not return the
        # assessments block - a degraded response, not a claim without
        # support. Counting domains over `supporting` there would score
        # every such claim as uncorroborated and cap it, i.e. silently
        # punish the claim for the model's output being malformed. Fall
        # back to what the older, stance-free scorer had: the evidence
        # the model said it cited.
        corroborating = supporting if llm_result.assessments else [
            item
            for index, item in enumerate(annotated)
            if index in set(llm_result.cited_evidence)
        ]

        independent_domains = len({
            item.domain or item.url for item in corroborating
        })

        confidence = max(0.0, min(
            llm_result.confidence * self.LLM_WEIGHT
            + self._evidence_quality(
                annotated,
                llm_result.cited_evidence,
                thresholds.max_evidence_per_claim,
            ) * self.EVIDENCE_WEIGHT,
            1.0,
        ))

        verdict = llm_result.verdict

        # A definitive verdict with zero citations, despite evidence being
        # available, is an ungrounded assertion - don't trust it.
        if verdict in _DEFINITIVE and not llm_result.cited_evidence:
            verdict = Verdict.UNVERIFIED
            confidence = min(confidence, 0.4)

        # Sources disagree about a claim the model called flatly true.
        # That is the ordinary shape of a real verification - the central
        # fact holds, some detail does not - and collapsing it into TRUE
        # discards the only part worth reading.
        elif verdict == Verdict.TRUE and contradicting:
            verdict = Verdict.PARTIALLY_TRUE

        # Corroborated by one outlet only. Not wrong, but not confirmed
        # either: a single source repeated is still a single source, which
        # is exactly what min_independent_domains exists to notice.
        elif (
            verdict == Verdict.TRUE
            and independent_domains < thresholds.min_independent_domains
        ):
            confidence = min(confidence, 0.6)

        return FactCheck(
            verdict=verdict,
            explanation=llm_result.explanation,
            confidence=confidence,
            claim=claim.text,
            evidence=annotated,
            cited_evidence_indices=llm_result.cited_evidence,
            evidence_count=len(annotated),
            agreements=self._summarise(supporting),
            discrepancies=self._summarise(contradicting),
            independent_domains=independent_domains,
        )

    ##########################################################

    @staticmethod
    def _annotate(
        evidence: list[Evidence],
        llm_result: LLMVerificationResult,
    ) -> list[Evidence]:
        """
        Copies each source's stance and validated quote onto the evidence
        itself, so everything downstream - the report, the API response,
        the UI - reads one object instead of joining two lists by index.
        """

        by_index = {
            assessment.index: assessment
            for assessment in llm_result.assessments
        }

        return [
            item.model_copy(update={
                "stance": by_index[index].stance,
                "quote": by_index[index].quote,
            })
            if index in by_index else item
            for index, item in enumerate(evidence)
        ]

    @staticmethod
    def _summarise(items: list[Evidence]) -> list[str]:
        """
        One line per source: what it is, and the span it was judged on
        where there is a verified one. Built from the stances rather than
        from the LLM's prose so the list and the explanation cannot tell
        different stories.
        """

        lines = []

        for item in items:

            source = item.domain or item.url

            lines.append(
                f"{source}: {item.quote}" if item.quote else source
            )

        return lines

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
