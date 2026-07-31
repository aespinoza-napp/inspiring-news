from src.models.nlp.sentiment_result import SentimentResult
from src.services.corrector.text_corrector import TextCorrector

from tests.fact_checker.fakes import FakeLLMClient


class FakeSentimentAnalyzer:

    def __init__(self, result: SentimentResult):
        self.result = result

    def process(self, text: str) -> SentimentResult:
        return self.result


class FakeQualityAnalyzer:

    def __init__(self, readability_score: float, quality_dict: dict):
        self.readability_score = readability_score
        self.quality_dict = quality_dict

    def readability(self, text: str) -> float:
        return self.readability_score

    def process(self, text: str, sentiment=None, entities=None, novelty=None) -> dict:
        return self.quality_dict


POSITIVE_SENTIMENT = SentimentResult(
    label="positive",
    positive=0.8,
    neutral=0.15,
    negative=0.05,
    polarity=0.75,
    subjectivity=0.3,
    confidence=0.9,
    emotional_intensity=0.75,
)

GOOD_QUALITY = dict(
    readability=0.8,
    objectivity=0.8,
    constructiveness=0.8,
    inspirational_score=0.8,
    hopefulness=0.8,
    societal_impact=0.8,
    novelty=0.5,
)


def make_corrector(llm_response=None) -> TextCorrector:

    return TextCorrector(
        llm=FakeLLMClient(responses=llm_response),
        sentiment_analyzer=FakeSentimentAnalyzer(POSITIVE_SENTIMENT),
        quality_analyzer=FakeQualityAnalyzer(0.8, GOOD_QUALITY),
    )


def test_readability_scales_quality_analyzer_score_to_0_100():

    corrector = make_corrector()

    metric = corrector._readability("some text")

    assert metric.score == 80.0


def test_coverage_reuses_positive_impact_validator():

    corrector = make_corrector()

    metric = corrector._coverage("some inspiring text")

    assert metric.score > 50.0
    assert "aligns well" in metric.summary.lower()


def test_llm_metrics_normalizes_full_response():

    corrector = make_corrector(llm_response={
        "grammar": {"score": 90, "summary": "Clean.", "issues": []},
        "factConsistency": {"score": 85, "summary": "Consistent.", "issues": []},
        "seo": {"score": 40, "summary": "Weak headline.", "issues": ["No keyword in title"]},
        "hallucinationIndex": {"score": 95, "summary": "Well-grounded.", "issues": []},
        "style": {"score": 70, "summary": "Fine.", "issues": []},
    })

    metrics = corrector._llm_metrics("some text")

    assert set(metrics.keys()) == {"grammar", "factConsistency", "seo", "hallucinationIndex", "style"}
    assert metrics["seo"].score == 40
    assert metrics["seo"].issues == ["No keyword in title"]


def test_llm_metrics_defaults_missing_keys():

    corrector = make_corrector(llm_response={"grammar": {"score": 90, "summary": "Clean."}})

    metrics = corrector._llm_metrics("some text")

    assert metrics["grammar"].score == 90
    assert metrics["style"].score == 0.0
    assert "unavailable" in metrics["style"].summary.lower()


def test_llm_metrics_defaults_when_client_returns_none():

    corrector = make_corrector(llm_response=None)

    metrics = corrector._llm_metrics("some text")

    assert all(metric.score == 0.0 for metric in metrics.values())


def test_correct_returns_all_seven_metrics():

    corrector = make_corrector(llm_response={
        "grammar": {"score": 90, "summary": "Clean."},
        "factConsistency": {"score": 85, "summary": "Consistent."},
        "seo": {"score": 40, "summary": "Weak."},
        "hallucinationIndex": {"score": 95, "summary": "Grounded."},
        "style": {"score": 70, "summary": "Fine."},
    })

    metrics = corrector.correct("some inspiring text")

    assert set(metrics.keys()) == {
        "grammar",
        "factConsistency",
        "coverageVerification",
        "seo",
        "readability",
        "hallucinationIndex",
        "style",
    }
