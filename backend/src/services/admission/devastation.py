from src.config.thresholds import PipelineThresholds
from src.models.admission.impact_result import ImpactResult
from src.models.nlp.quality import Quality
from src.models.nlp.sentiment_result import SentimentResult


class DevastationScorer:
    """
    The Devastating edition's tone gate (docs/decisions/editions.md): how
    much harm to people the article reports, on a 0-1 scale, and whether
    that clears the run's minimum. PositiveImpactScorer's mirror, with the
    same inputs and the same result, so AdmissionFilter can ask either.

    Not simply PositiveImpactScorer turned upside down. That score is
    mostly constructiveness, inspiration and hope, and a story *lacking*
    those is as often a dull council minute as a massacre. What a
    devastating story has is negative sentiment about something that
    matters to many people - so the two lead here, and hope costs.

    Objectivity still counts for, and a hard fail on very low objectivity
    is kept: the edition's stories are checked like any other, and a rant
    is not news however bleak.
    """

    # The positive weights below, so the score lands on 0-1.
    WEIGHT_SUM = 2.40

    def score(
        self,
        sentiment: SentimentResult,
        quality: Quality,
        thresholds: PipelineThresholds | None = None,
    ) -> ImpactResult:

        resolved = thresholds or PipelineThresholds()
        minimum = resolved.devastation_min_score

        reasons = []

        score = (
            sentiment.negative * 1.00
            + quality.societal_impact * 1.00
            + quality.objectivity * 0.20
            + sentiment.emotional_intensity * 0.20
        )

        # Heavy enough that societal impact alone cannot carry a hopeful
        # story through: the suite's own hopeful article (societal impact
        # 0.8, hope 0.8) cleared the gate at 0.30 each.
        score -= quality.hopefulness * 0.60
        score -= quality.inspirational_score * 0.60

        score /= self.WEIGHT_SUM

        if sentiment.negative < 0.30:
            reasons.append("Not negative enough")

        if quality.societal_impact < 0.20:
            reasons.append("Low societal impact")

        if quality.objectivity < 0.25:
            reasons.append("Low objectivity")

        if quality.hopefulness > 0.60:
            reasons.append("Too hopeful")

        hard_fail = quality.objectivity < 0.10

        return ImpactResult(
            passed=not hard_fail and score >= minimum,
            score=max(0.0, min(score, 1.0)),
            reasons=reasons,
        )
