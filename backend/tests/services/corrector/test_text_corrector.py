from src.models.nlp.sentiment_result import SentimentResult
from src.services.corrector.text_corrector import TextCorrector

from tests.services.fact_checker.fakes import (
    FakeLLMClient,
    FakeQualityAnalyzer,
    FakeSentimentAnalyzer,
)


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

    metrics = corrector.llm_metrics("some text")

    assert set(metrics.keys()) == {"grammar", "factConsistency", "seo", "hallucinationIndex", "style"}
    assert metrics["seo"].score == 40
    assert metrics["seo"].issues == ["No keyword in title"]


def test_llm_metrics_defaults_missing_keys():

    corrector = make_corrector(llm_response={"grammar": {"score": 90, "summary": "Clean."}})

    metrics = corrector.llm_metrics("some text")

    assert metrics["grammar"].score == 90
    assert metrics["style"].score == 0.0
    assert "unavailable" in metrics["style"].summary.lower()


def test_llm_metrics_defaults_when_client_returns_none():

    corrector = make_corrector(llm_response=None)

    metrics = corrector.llm_metrics("some text")

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


def test_null_issues_lose_nothing_but_the_list():
    """`"issues": null` raised TypeError and lost all five metrics."""

    corrector = make_corrector(llm_response={
        "grammar": {"score": 90, "summary": "Clean.", "issues": None},
        "style": {"score": 70, "summary": "Fine.", "issues": "One long sentence."},
    })

    metrics = corrector.llm_metrics("some text")

    assert metrics["grammar"].score == 90
    assert metrics["grammar"].issues == []
    assert metrics["style"].issues == ["One long sentence."]


def test_a_score_that_is_not_a_number_is_unavailable_not_zero():
    """
    The writing benchmark averages these per model: a 0 standing in for
    "high" or a missing score would read as the harshest judgement.
    """

    corrector = make_corrector(llm_response={
        "grammar": {"score": "high", "summary": "Clean."},
        "factConsistency": {"summary": "No score at all."},
        "seo": {"score": None, "summary": "Null."},
        "hallucinationIndex": {"score": float("nan"), "summary": "NaN."},
        "style": {"score": "85", "summary": "A numeric string is still a number."},
    })

    metrics = corrector.llm_metrics("some text")

    for key in ("grammar", "factConsistency", "seo", "hallucinationIndex"):
        assert metrics[key].score == 0.0
        assert "unavailable" in metrics[key].summary.lower(), key

    assert metrics["style"].score == 85
