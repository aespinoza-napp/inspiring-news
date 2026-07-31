from datetime import datetime

from src.models.news import News
from src.services.fact_checker.retrieval.scraper import EvidenceScraper

from tests.factories import create_evidence
from tests.fact_checker.fakes import FakeExtractorService


def test_enrich_populates_content_from_scraped_news():

    news = News(
        source_id="web",
        url="https://example.com/a",
        title="Scraped title",
        published_at=datetime(2024, 1, 1),
        content="Full scraped article body.",
    )

    scraper = EvidenceScraper(extractor=FakeExtractorService({
        "https://example.com/a": news,
    }))

    evidence = create_evidence(url="https://example.com/a", title="", published_at=None)

    result = scraper.enrich([evidence])

    assert result[0].content == "Full scraped article body."
    assert result[0].title == "Scraped title"
    assert result[0].published_at == datetime(2024, 1, 1)


def test_enrich_keeps_original_title_when_present():

    news = News(
        source_id="web",
        url="https://example.com/a",
        title="Scraped title",
        published_at=datetime(2024, 1, 1),
        content="Full scraped article body.",
    )

    scraper = EvidenceScraper(extractor=FakeExtractorService({
        "https://example.com/a": news,
    }))

    evidence = create_evidence(url="https://example.com/a", title="Original title")

    result = scraper.enrich([evidence])

    assert result[0].title == "Original title"


def test_enrich_keeps_original_evidence_when_extraction_returns_none():

    scraper = EvidenceScraper(extractor=FakeExtractorService({
        "https://example.com/a": None,
    }))

    evidence = create_evidence(url="https://example.com/a")

    result = scraper.enrich([evidence])

    assert result[0] == evidence


def test_enrich_keeps_original_evidence_on_scrape_error():

    scraper = EvidenceScraper(extractor=FakeExtractorService({
        "https://example.com/a": RuntimeError("boom"),
    }))

    evidence = create_evidence(url="https://example.com/a")

    result = scraper.enrich([evidence])

    assert result[0] == evidence
