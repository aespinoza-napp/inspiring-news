from unittest.mock import Mock

from src.services.scraper.scraper import Scraper

from tests.builders.source_builder import build_source


def make_scraper(discover_return=None, extract_return=None) -> Scraper:

    scraper = Scraper()

    scraper.discovery = Mock()
    scraper.discovery.discover.return_value = discover_return or []

    scraper.extractor = Mock()
    scraper.extractor.extract.return_value = extract_return

    return scraper


def test_discover_delegates_to_discovery_service():

    source = build_source()

    scraper = make_scraper(discover_return=["https://bbc.com/a", "https://bbc.com/b"])

    urls = scraper.discover(source, topics=["space"])

    assert urls == ["https://bbc.com/a", "https://bbc.com/b"]

    scraper.discovery.discover.assert_called_once_with(
        source=source,
        topics=["space"],
    )


def test_extract_delegates_to_extractor_service():

    source = build_source()

    fake_news = Mock()
    scraper = make_scraper(extract_return=fake_news)

    result = scraper.extract(source, "https://bbc.com/a")

    assert result is fake_news

    scraper.extractor.extract.assert_called_once_with(source, "https://bbc.com/a")


def test_extract_returns_none_when_extractor_finds_nothing():

    source = build_source()

    scraper = make_scraper(extract_return=None)

    assert scraper.extract(source, "https://bbc.com/a") is None
