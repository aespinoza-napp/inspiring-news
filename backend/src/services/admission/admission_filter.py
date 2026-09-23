from dataclasses import dataclass, field
from typing import Callable, Optional

from src.config.thresholds import PipelineThresholds
from src.models.core.enriched_article import EnrichedArticle
from src.repositories.vector_repository import VectorRepository
from src.services.admission.duplicate_detector import DuplicateDetector
from src.services.admission.positive_impact import PositiveImpactScorer
from src.services.admission.topic_filter import TopicFilter

OnPhase = Callable[[str, dict], None]


def _noop(phase: str, data: dict) -> None:
    pass


@dataclass
class AdmissionResult:

    passed: bool

    topic_ok: bool

    positive_ok: bool

    duplicate: bool

    impact_score: float

    impact_reasons: list[str] = field(default_factory=list)

    @property
    def reason(self) -> str | None:
        """
        Why the article was turned away, as the comma-joined codes the
        report and the frontend already read. None when it was admitted.
        """

        if self.passed:
            return None

        reasons = []

        if not self.topic_ok:
            reasons.append("topic_not_relevant")

        if not self.positive_ok:
            reasons.append("not_positive_impact")

        if self.duplicate:
            reasons.append("duplicate_article")

        return ",".join(reasons) or "validation_failed"


class AdmissionFilter:
    """
    Decides whether an enriched article is worth fact-checking at all:
    on topic, of positive impact, and not already stored.

    A module of its own, run before the fact-checker rather than inside
    it. The three checks judge an *article* - its topics, its tone, its
    neighbours in the vector store - and none of them needs evidence, a
    search or an LLM; the fact-checker judges *claims* and needs all
    three. Kept apart, each can be called, tested and replaced without
    the other: the corrector scores impact on text that will never be
    fact-checked, and /verify-claim fact-checks a claim that has no
    article to admit.

    All three always run, even when an earlier one has already failed,
    so the report can say every reason an article was turned away.
    """

    def __init__(
        self,
        repository: VectorRepository,
        topic_filter: TopicFilter | None = None,
        impact_scorer: PositiveImpactScorer | None = None,
        duplicate_detector: DuplicateDetector | None = None,
    ):

        self.topic_filter = topic_filter or TopicFilter()

        self.impact_scorer = impact_scorer or PositiveImpactScorer()

        self.duplicate_detector = duplicate_detector or DuplicateDetector(repository)

    def admit(
        self,
        article: EnrichedArticle,
        thresholds: PipelineThresholds | None = None,
        on_phase: Optional[OnPhase] = None,
    ) -> AdmissionResult:

        report_phase = on_phase or _noop

        thresholds = thresholds or PipelineThresholds()

        report_phase("validating", {})

        topic_ok = self.topic_filter.accepts(article, thresholds)

        impact = self.impact_scorer.score(
            article.sentiment,
            article.quality,
            thresholds,
        )

        duplicate = self.duplicate_detector.check(article, thresholds)

        result = AdmissionResult(
            passed=(
                topic_ok
                and impact.passed
                and not duplicate.duplicate
            ),
            topic_ok=topic_ok,
            positive_ok=impact.passed,
            duplicate=duplicate.duplicate,
            impact_score=impact.score,
            impact_reasons=impact.reasons,
        )

        report_phase("validated", {
            "topicOk": result.topic_ok,
            "positiveOk": result.positive_ok,
            "duplicate": result.duplicate,
            "passed": result.passed,
            "impactScore": result.impact_score,
            "impactReasons": result.impact_reasons,
        })

        if not result.passed:
            report_phase("skipped", {"reason": result.reason})

        return result

    def remember(self, article: EnrichedArticle) -> None:
        """
        Record an admitted, checked article so the next copy of it is
        caught as a duplicate. See DuplicateDetector.remember for why this
        waits until after the fact-check.
        """

        self.duplicate_detector.remember(article)
