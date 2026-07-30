
from src.models.sentiment_result import SentimentResult
from src.models.quality import Quality
from src.models.validation_result import ValidationResult




class PositiveImpactValidator:

    MIN_SCORE = 0.55

    def validate(
        self,
        sentiment: SentimentResult,
        quality: Quality,
    ) -> ValidationResult:

        reasons = []

        score = (
            quality.constructiveness * 0.30
            + quality.inspirational_score * 0.25
            + quality.hopefulness * 0.15
            + sentiment.positive * 0.10
            + quality.objectivity * 0.10
            + quality.societal_impact * 0.10
            #+ quality.readability * 0.05
        )

        score -= sentiment.negative * 0.15
        score -= sentiment.subjectivity * 0.05

        if quality.constructiveness < 0.30:
            reasons.append("Low constructiveness")

        if quality.inspirational_score < 0.25:
            reasons.append("Low inspirational value")

        if quality.objectivity < 0.25:
            reasons.append("Low objectivity")

        if sentiment.negative > 0.70:
            reasons.append("Strong negative sentiment")

        hard_fail = (
            quality.constructiveness < 0.30
            or quality.inspirational_score < 0.25
            or quality.objectivity < 0.25
            or sentiment.negative > 0.70
        )

        passed = not hard_fail and score >= self.MIN_SCORE

        return ValidationResult(
            passed=passed,
            score=max(0.0, min(score, 1.0)),
            reasons=reasons,
        )