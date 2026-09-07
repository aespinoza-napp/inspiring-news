
from src.models.nlp.sentiment_result import SentimentResult
from src.models.nlp.quality import Quality
from src.models.fact_checker.validation_result import ValidationResult




class PositiveImpactValidator:

    MIN_SCORE = 0.3

    def validate(
        self,
        sentiment: SentimentResult,
        quality: Quality,
    ) -> ValidationResult:

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

        if quality.constructiveness < 0.20:
            reasons.append("Low constructiveness")

        if quality.inspirational_score < 0.15:
            reasons.append("Low inspirational value")

        if quality.objectivity < 0.25:
            reasons.append("Low objectivity")

        if sentiment.negative > 0.70:
            reasons.append("Strong negative sentiment")
        
        hard_fail = (
            #quality.constructiveness < 0.20
            #quality.inspirational_score < 0.15
            quality.objectivity < 0.25
            or sentiment.negative > 0.70
        )

        passed = not hard_fail and score >= self.MIN_SCORE
        
        return ValidationResult(
            passed=passed,
            score=max(0.0, min(score, 1.0)),
            reasons=reasons,
        )
