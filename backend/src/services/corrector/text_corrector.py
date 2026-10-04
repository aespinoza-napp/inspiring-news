import math

from src.config.settings import settings
from src.models.corrector.correction_metric import CorrectionMetric
from src.models.nlp.quality import Quality
from src.config.lexicons import lexicon_for
from src.processors.nlp.language import LanguageDetector
from src.processors.nlp.quality import QualityAnalyzer
from src.processors.nlp.sentiment import SentimentAnalyzer
from src.services.admission.positive_impact import (
    PositiveImpactScorer,
)
from src.services.llms import LLMClient

LLM_METRIC_KEYS = ("grammar", "factConsistency", "seo", "hallucinationIndex", "style")

# What a metric says when the model did not return a usable entry for it.
# A constant so the writing benchmark can count these per model: failing
# the output format is part of what it measures, and a copy of this
# sentence there would stop matching the day it is reworded here.
UNAVAILABLE_SUMMARY = (
    "Evaluation unavailable - the LLM did not return a usable result for this metric."
)

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
        impact_scorer: PositiveImpactScorer | None = None,
    ):
        self.llm = llm or LLMClient()
        self.sentiment_analyzer = sentiment_analyzer or SentimentAnalyzer(settings)
        self.quality_analyzer = quality_analyzer or QualityAnalyzer()
        self.impact_scorer = impact_scorer or PositiveImpactScorer()

    def correct(self, text: str) -> dict[str, CorrectionMetric]:

        # Both deterministic metrics are keyword/formula based, so both
        # need the text's language or they silently score Spanish input
        # against English word lists and the English Flesch formula.
        language = LanguageDetector.detect(text)

        metrics = {
            "readability": self._readability(text, language),
            "coverageVerification": self._coverage(text, language),
        }

        metrics.update(self.llm_metrics(text))

        return metrics

    def _readability(self, text: str, language: str = "en") -> CorrectionMetric:

        score = self.quality_analyzer.readability(
            text, lexicon_for(language)
        ) * 100

        return CorrectionMetric(
            score=round(score, 1),
            summary="Flesch reading ease scaled to 0-100 (higher = easier to read).",
        )

    def _coverage(self, text: str, language: str = "en") -> CorrectionMetric:

        sentiment = self.sentiment_analyzer.process(text)

        quality = Quality(
            **self.quality_analyzer.process(
                text, sentiment=sentiment, language=language
            )
        )

        result = self.impact_scorer.score(sentiment, quality)

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

    def llm_metrics(self, text: str) -> dict[str, CorrectionMetric]:
        """
        The five model-dependent metrics, from one LLM call.

        Public because the writing benchmark (src/evaluation/writing.py)
        runs exactly this per model: the two deterministic metrics do not
        depend on the model, and benchmarking a copy of this call would
        measure the copy.

        Raises LLMUnavailableError when the provider was never reached,
        as complete_json does; an answer that is not usable JSON comes
        back as UNAVAILABLE_SUMMARY on every metric instead.
        """

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
                summary=UNAVAILABLE_SUMMARY,
            )

        # A missing or non-numeric score is a format failure, not a 0: the
        # writing benchmark averages scores per model, and a 0 standing in
        # for "high" or null would read as the harshest judgement.
        try:
            score = float(item["score"])
        except (KeyError, TypeError, ValueError):
            score = math.nan

        if not math.isfinite(score):
            return CorrectionMetric(
                score=0.0,
                summary=UNAVAILABLE_SUMMARY,
            )

        score = max(0.0, min(score, 100.0))

        # `or []`: a model that sends "issues": null otherwise raised
        # TypeError here and lost all five metrics, not just this list.
        raw_issues = item.get("issues") or []

        issues = [
            str(issue)
            for issue in (raw_issues if isinstance(raw_issues, list) else [raw_issues])
            if isinstance(issue, (str, int, float))
        ]

        return CorrectionMetric(
            score=score,
            summary=str(item.get("summary") or "No summary provided.").strip(),
            issues=issues,
        )
