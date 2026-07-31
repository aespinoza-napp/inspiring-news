from src.config.settings import settings
from src.models.corrector.correction_metric import CorrectionMetric
from src.models.nlp.quality import Quality
from src.processors.nlp.quality import QualityAnalyzer
from src.processors.nlp.sentiment import SentimentAnalyzer
from src.services.fact_checker.validators.positive_impact_validator import (
    PositiveImpactValidator,
)
from src.services.llms import LLMClient

LLM_METRIC_KEYS = ("grammar", "factConsistency", "seo", "hallucinationIndex", "style")

SYSTEM_PROMPT = (
    "You are an expert editor evaluating a piece of writing for a "
    "positive/inspiring news publication. Score the text on each of these "
    "dimensions, 0-100 (higher is always better, INCLUDING "
    "hallucinationIndex - a high hallucinationIndex score means the text "
    "is well-supported and free of fabrication, a low score means it "
    "reads as fabricated or unsupported):\n"
    "- grammar: grammatical correctness and clarity\n"
    "- factConsistency: internal consistency - does the text contradict itself?\n"
    "- seo: search-engine friendliness (headline clarity, keyword usage, structure)\n"
    "- hallucinationIndex: how well-grounded the text is (see above)\n"
    "- style: writing quality/voice appropriate for a news article\n\n"
    "Respond with ONLY a JSON object of this exact shape, one entry per "
    "dimension above:\n"
    '{"grammar": {"score": <0-100>, "summary": "<1-2 sentences>", '
    '"issues": ["..."]}, "factConsistency": {...}, "seo": {...}, '
    '"hallucinationIndex": {...}, "style": {...}}'
)


class TextCorrector:
    """
    Produces the 7 "corrector" metrics. Readability and coverageVerification
    are deterministic, reusing the same processors/validators the main
    pipeline already relies on rather than asking an LLM to guess at them.
    The remaining 5 (grammar/factConsistency/seo/hallucinationIndex/style)
    come from a single LLM call.
    """

    def __init__(
        self,
        llm: LLMClient | None = None,
        sentiment_analyzer=None,
        quality_analyzer: QualityAnalyzer | None = None,
        positive_validator: PositiveImpactValidator | None = None,
    ):
        self.llm = llm or LLMClient()
        self.sentiment_analyzer = sentiment_analyzer or SentimentAnalyzer(settings)
        self.quality_analyzer = quality_analyzer or QualityAnalyzer()
        self.positive_validator = positive_validator or PositiveImpactValidator()

    def correct(self, text: str) -> dict[str, CorrectionMetric]:

        metrics = {
            "readability": self._readability(text),
            "coverageVerification": self._coverage(text),
        }

        metrics.update(self._llm_metrics(text))

        return metrics

    def _readability(self, text: str) -> CorrectionMetric:

        score = self.quality_analyzer.readability(text) * 100

        return CorrectionMetric(
            score=round(score, 1),
            summary="Flesch reading ease scaled to 0-100 (higher = easier to read).",
        )

    def _coverage(self, text: str) -> CorrectionMetric:

        sentiment = self.sentiment_analyzer.process(text)

        quality = Quality(
            **self.quality_analyzer.process(text, sentiment=sentiment)
        )

        result = self.positive_validator.validate(sentiment, quality)

        summary = (
            "Aligns well with Inspiring's positive-impact criteria."
            if result.passed
            else "Does not fully align with Inspiring's positive-impact criteria."
        )

        return CorrectionMetric(
            score=round(result.score * 100, 1),
            summary=summary,
            issues=result.reasons,
        )

    def _llm_metrics(self, text: str) -> dict[str, CorrectionMetric]:

        result = self.llm.complete_json(SYSTEM_PROMPT, text)

        return {
            key: self._normalize(result, key)
            for key in LLM_METRIC_KEYS
        }

    def _normalize(self, result: dict | None, key: str) -> CorrectionMetric:

        item = result.get(key) if isinstance(result, dict) else None

        if not isinstance(item, dict):
            return CorrectionMetric(
                score=0.0,
                summary="Evaluation unavailable - the LLM did not return a usable result for this metric.",
            )

        try:
            score = max(0.0, min(float(item.get("score", 0.0)), 100.0))
        except (TypeError, ValueError):
            score = 0.0

        issues = [
            str(issue)
            for issue in item.get("issues", [])
            if isinstance(issue, (str, int, float))
        ]

        return CorrectionMetric(
            score=score,
            summary=str(item.get("summary") or "No summary provided.").strip(),
            issues=issues,
        )
