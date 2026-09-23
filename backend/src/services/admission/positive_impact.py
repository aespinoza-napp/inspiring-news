
from src.config.thresholds import PipelineThresholds
from src.models.nlp.sentiment_result import SentimentResult
from src.models.nlp.quality import Quality
from src.models.admission.impact_result import ImpactResult




class PositiveImpactScorer:
    """
    How constructive, inspiring and hopeful the article is, on a 0-1
    scale, and whether that clears the run's minimum.

    Takes sentiment and quality rather than an article so anything
    holding those two can be scored - the corrector reuses it for its
    coverage metric on text that is not an article at all.
    """

    # settings.POSITIVE_IMPACT_MIN_SCORE is the default; a single run can
    # override it (see src/config/thresholds.py).

    # Positive weights below sum to 3.50, so the raw score ran to 3.50
    # while the returned score was clamped to 1.0 - which meant almost
    # every article reported impact_score == 1.0 exactly, and the
    # `score >= MIN_SCORE` gate could never fire (even an article scoring
    # 0 on all three primary signals still cleared 0.3 on the secondary
    # ones alone). Dividing by the positive weight sum puts the score
    # back on a real 0-1 scale and makes both the number and the gate
    # mean something.
    WEIGHT_SUM = 3.50

    def score(
        self,
        sentiment: SentimentResult,
        quality: Quality,
        thresholds: PipelineThresholds | None = None,
    ) -> ImpactResult:

        resolved = thresholds or PipelineThresholds()
        minimum = resolved.positive_impact_min_score

        reasons = []

        score = (
            quality.constructiveness * 1.00
            + quality.inspirational_score * 1.00
            + quality.hopefulness * 1.00
            + sentiment.positive * 0.15
            + quality.objectivity * 0.10
            + quality.societal_impact * 0.15
            + quality.readability * 0.10
        )

        score -= sentiment.negative * 0.15
        score -= sentiment.subjectivity * 0.10

        score /= self.WEIGHT_SUM

        if quality.constructiveness < 0.20:
            reasons.append("Low constructiveness")

        if quality.inspirational_score < 0.15:
            reasons.append("Low inspirational value")

        if quality.objectivity < 0.25:
            reasons.append("Low objectivity")

        if sentiment.negative > 0.70:
            reasons.append("Strong negative sentiment")

        # constructiveness/inspirational-score hard fails are deliberately
        # never applied - see test_low_constructiveness_is_flagged_but_not_a_hard_fail.
        hard_fail = resolved.positive_impact_hard_fail_enabled and (
            quality.objectivity < 0.25
            or sentiment.negative > 0.70
        )

        passed = not hard_fail and score >= minimum
        
        return ImpactResult(
            passed=passed,
            score=max(0.0, min(score, 1.0)),
            reasons=reasons,
        )
