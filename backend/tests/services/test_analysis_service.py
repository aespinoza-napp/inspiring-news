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


def make_service(extract_return, article, report) -> AnalysisService:

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
    }

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
