from datetime import datetime
from unittest.mock import Mock

from src.models.core.news import News
from src.models.fact_checker.fact_check import FactCheck, Verdict
from src.models.fact_checker.fact_check_report import FactCheckReport
from src.services.analysis_service import AnalysisService

from tests.factories import create_article, create_claim


def make_news(**kwargs) -> News:

    defaults = dict(
        source_id="web",
        url="https://example.com/a",
        title="A title",
        published_at=datetime(2024, 1, 1),
        content="Some article content.",
    )

    defaults.update(kwargs)

    return News(**defaults)


class FakeCache:

    def __init__(self):
        self.store = {}

    def get(self, url):
        return self.store.get(url)

    def set(self, url, result):
        self.store[url] = result


def make_service(extract_return, article, report, cache=None) -> AnalysisService:

    extractor = Mock()
    extractor.extract.return_value = extract_return

    enrichment_pipeline = Mock()
    enrichment_pipeline.process.return_value = article

    fact_checker = Mock()
    fact_checker.run.return_value = report

    return AnalysisService(
        fact_checker=fact_checker,
        extractor=extractor,
        enrichment_pipeline=enrichment_pipeline,
        cache=cache if cache is not None else FakeCache(),
    )


def test_analyze_returns_error_when_extraction_fails():

    service = make_service(extract_return=None, article=None, report=None)

    result = service.analyze("https://example.com/a")

    assert result["url"] == "https://example.com/a"
    assert "error" in result


def test_analyze_returns_error_on_extractor_exception():

    extractor = Mock()
    extractor.extract.side_effect = RuntimeError("boom")

    service = AnalysisService(
        fact_checker=Mock(),
        extractor=extractor,
        enrichment_pipeline=Mock(),
        cache=FakeCache(),
    )

    result = service.analyze("https://example.com/a")

    assert "error" in result


def test_analyze_shapes_successful_result_with_sorted_claims():

    article = create_article(
        title="Test article",
        keywords=["mars", "water"],
        entities={"organization": ["NASA"]},
    )

    checks = [
        FactCheck(
            verdict=Verdict.TRUE,
            explanation="Confirmed.",
            confidence=0.9,
            claim="A true claim.",
            evidence_count=2,
        ),
        FactCheck(
            verdict=Verdict.FALSE,
            explanation="Contradicted.",
            confidence=0.8,
            claim="A false claim.",
            evidence_count=3,
        ),
    ]

    report = FactCheckReport(
        article_id=article.id,
        validation_passed=True,
        topic_ok=True,
        positive_ok=True,
        duplicate=False,
        claims_total=2,
        claims_selected=2,
        claim_checks=checks,
        overall_verdict=Verdict.FALSE,
        overall_confidence=0.85,
    )

    service = make_service(make_news(), article, report)

    result = service.analyze("https://example.com/a")

    assert result["title"] == "Test article"
    assert result["keywords"] == ["mars", "water"]
    assert result["entities"] == {"organization": ["NASA"]}

    # worst verdict (FALSE) sorted first
    assert [c["verdict"] for c in result["claims"]] == [Verdict.FALSE, Verdict.TRUE]

    assert result["validity"] == {
        "isValid": True,
        "isDuplicate": False,
        "hasTopic": True,
        "reasons": [],
        "impactScore": 0.0,
        "impactReasons": [],
    }

    assert result["sentiment"]["label"] == "neutral"
    assert result["sentiment"]["emotionalIntensity"] == 0.2
    assert result["quality"]["constructiveness"] == 0.8

    assert result["factCheck"]["overallVerdict"] == Verdict.FALSE
    assert result["factCheck"]["claimsChecked"] == 2


def test_analyze_falls_back_to_raw_claims_when_validation_failed():

    claim = create_claim(text="Unchecked claim.", confidence=0.7)

    article = create_article(claims=[claim])

    report = FactCheckReport(
        article_id=article.id,
        validation_passed=False,
        skipped_reason="topic_not_relevant",
        topic_ok=False,
        positive_ok=True,
        duplicate=False,
        claims_total=1,
        claims_selected=0,
        claim_checks=[],
    )

    service = make_service(make_news(), article, report)

    result = service.analyze("https://example.com/a")

    assert result["validity"]["isValid"] is False
    assert result["validity"]["hasTopic"] is False
    assert result["validity"]["reasons"] == ["topic_not_relevant"]

    assert result["claims"] == [
        {
            "text": "Unchecked claim.",
            "confidence": 0.7,
            "verdict": None,
            "explanation": None,
            "evidenceCount": 0,
        }
    ]


def _successful_report(article) -> FactCheckReport:

    return FactCheckReport(
        article_id=article.id,
        validation_passed=True,
        topic_ok=True,
        positive_ok=True,
        duplicate=False,
        claims_total=0,
        claims_selected=0,
    )


def test_analyze_returns_cached_result_without_running_pipeline():

    cache = FakeCache()
    cache.store["https://example.com/a"] = {"url": "https://example.com/a", "title": "Cached"}

    extractor = Mock()
    enrichment_pipeline = Mock()
    fact_checker = Mock()

    service = AnalysisService(
        fact_checker=fact_checker,
        extractor=extractor,
        enrichment_pipeline=enrichment_pipeline,
        cache=cache,
    )

    result = service.analyze("https://example.com/a")

    assert result["title"] == "Cached"
    assert result["cached"] is True

    extractor.extract.assert_not_called()
    enrichment_pipeline.process.assert_not_called()
    fact_checker.run.assert_not_called()


def test_analyze_caches_successful_result_for_next_call():

    article = create_article()
    cache = FakeCache()

    service = make_service(make_news(), article, _successful_report(article), cache=cache)

    first = service.analyze("https://example.com/a")

    assert first["cached"] is False
    assert cache.get("https://example.com/a") is not None

    second = service.analyze("https://example.com/a")

    assert second["cached"] is True
    # Only the first call should have touched the pipeline.
    service.extractor.extract.assert_called_once()


def test_analyze_does_not_cache_errors():

    cache = FakeCache()

    service = make_service(extract_return=None, article=None, report=None, cache=cache)

    service.analyze("https://example.com/a")

    assert cache.get("https://example.com/a") is None


def test_analyze_force_refresh_bypasses_and_overwrites_cache():

    article = create_article()
    cache = FakeCache()
    cache.store["https://example.com/a"] = {"url": "https://example.com/a", "title": "Stale"}

    service = make_service(make_news(), article, _successful_report(article), cache=cache)

    result = service.analyze("https://example.com/a", force_refresh=True)

    assert result["cached"] is False
    assert result["title"] != "Stale"
    service.extractor.extract.assert_called_once()

    assert cache.get("https://example.com/a")["title"] != "Stale"


def test_analyze_reports_phases_in_order():

    article = create_article(title="Phased article")
    report = _successful_report(article)

    fact_checker = Mock()

    def run_with_phases(article, on_phase=None):
        if on_phase:
            on_phase("validating", {})
            on_phase("fact_check_done", {"overallVerdict": report.overall_verdict})
        return report

    fact_checker.run.side_effect = run_with_phases

    extractor = Mock()
    extractor.extract.return_value = make_news()

    enrichment_pipeline = Mock()
    enrichment_pipeline.process.return_value = article

    service = AnalysisService(
        fact_checker=fact_checker,
        extractor=extractor,
        enrichment_pipeline=enrichment_pipeline,
        cache=FakeCache(),
    )

    events = []

    service.analyze("https://example.com/a", on_phase=lambda phase, data: events.append(phase))

    assert events == [
        "scraping",
        "scraped",
        "enriching",
        "enriched",
        "validating",
        "fact_check_done",
        "done",
    ]


def test_analyze_reports_cache_hit_instead_of_pipeline_phases():

    cache = FakeCache()
    cache.store["https://example.com/a"] = {"url": "https://example.com/a", "title": "Cached"}

    service = AnalysisService(
        fact_checker=Mock(),
        extractor=Mock(),
        enrichment_pipeline=Mock(),
        cache=cache,
    )

    events = []

    service.analyze("https://example.com/a", on_phase=lambda phase, data: events.append(phase))

    assert events == ["cache_hit"]


def test_analyze_reports_failed_phase_on_extraction_error():

    service = make_service(extract_return=None, article=None, report=None)

    events = []

    service.analyze("https://example.com/a", on_phase=lambda phase, data: events.append(phase))

    assert events == ["scraping", "failed"]
