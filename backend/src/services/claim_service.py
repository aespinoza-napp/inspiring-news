from logging import getLogger
from typing import Callable, Optional

from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim
from src.models.fact_checker.fact_check import FactCheck
from src.processors.nlp.entities import EntityExtractor
from src.services.fact_checker.fact_checker import FactChecker

logger = getLogger(__name__)

OnPhase = Callable[[str, dict], None]


def _noop(phase: str, data: dict) -> None:
    pass


class ClaimService:
    """
    Verifies a single claim supplied directly by a user, without an
    article around it.

    This is the article pipeline's verification stage used on its own:
    the same EvidenceRetriever -> EvidenceRanker -> LLMVerifier ->
    ConfidenceScorer chain, reached through FactChecker.check_claim, so
    a claim checked here and the same claim checked inside an article
    run cannot reach different conclusions.

    What it deliberately skips is everything that judges an *article*:
    the admission filter (topic relevance, positive impact, duplicate
    detection) and claim selection. A bare claim has no topic score and
    no article to be a duplicate of, and gating on those would reject
    perfectly checkable claims for reasons that do not apply to them.
    """

    def __init__(
        self,
        fact_checker: FactChecker,
        entity_extractor: EntityExtractor | None = None,
    ):
        self.fact_checker = fact_checker

        # Reused, not reimplemented: the claim's entities come from the
        # same GLiNER pass the article pipeline uses. Lazy, because
        # constructing one loads GLiNER - the app passes the container's
        # singleton instead.
        self._entity_extractor = entity_extractor

    @property
    def entity_extractor(self) -> EntityExtractor:

        if self._entity_extractor is None:
            self._entity_extractor = EntityExtractor()

        return self._entity_extractor

    def verify(
        self,
        text: str,
        on_phase: Optional[OnPhase] = None,
        thresholds: PipelineThresholds | None = None,
    ) -> dict:

        report_phase = on_phase or _noop

        thresholds = thresholds or PipelineThresholds()

        claim = self.build_claim(text, report_phase, thresholds)

        report_phase("verifying", {"claim": claim.text})

        check = self.fact_checker.check_claim(
            claim,
            on_phase=report_phase,
            thresholds=thresholds,
        )

        result = self._shape(claim, check, thresholds)

        report_phase("done", result)

        return result

    def build_claim(
        self,
        text: str,
        report_phase: OnPhase,
        thresholds: PipelineThresholds,
    ) -> Claim:

        report_phase("extracting_entities", {})

        entities = self.entity_extractor.process(
            text,
            thresholds.entity_threshold,
        )

        # confidence=1.0, not a computed check-worthiness score: inside an
        # article, confidence ranks sentences against each other to pick
        # which are worth checking. Here the user has already made that
        # choice by submitting this claim, so scoring it would only risk
        # discarding it.
        return Claim(text=text.strip(), entities=entities, confidence=1.0)

    @staticmethod
    def _shape(
        claim: Claim,
        check: FactCheck,
        thresholds: PipelineThresholds,
    ) -> dict:

        cited = set(check.cited_evidence_indices)

        return {
            "claim": claim.text,
            "entities": claim.entities,
            "verdict": check.verdict,
            "confidence": check.confidence,
            "explanation": check.explanation,
            "evidenceCount": check.evidence_count,
            "evidence": [
                {
                    "url": item.url,
                    "title": item.title,
                    "snippet": item.snippet,
                    "origin": item.origin,
                    "relevanceScore": item.relevance_score,
                    "sourceReliability": item.source_reliability,
                    "publishedAt": item.published_at,
                    "cited": index in cited,
                }
                for index, item in enumerate(check.evidence)
            ],
            "rejectedSources": [
                {
                    "url": source.url,
                    "title": source.title,
                    "origin": source.origin,
                    "stage": source.stage,
                    "reason": source.reason,
                    "score": source.score,
                }
                for source in check.rejected_sources
            ],
            "reachedStage": check.reached_stage,
            "stageNote": check.stage_note,
            "rawVerdict": check.raw_verdict,
            "rawConfidence": check.raw_confidence,
            "thresholds": thresholds.model_dump(),
        }
