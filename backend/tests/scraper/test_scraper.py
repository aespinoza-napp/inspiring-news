from unittest.mock import Mock

from src.services.scraper.scraper import Scraper


def test_discover_delegates():

    scraper = Scraper()

    scraper.discovery = Mock()
    scraper.discovery.discover.return_value = ["url1"]

    urls = scraper.discover(source="source")

    scraper.discovery.discover.assert_called_once_with("source")
    assert urls == ["url1"]


def test_extract_delegates():

    scraper = Scraper()

    scraper.extractor = Mock()
    scraper.extractor.extract.return_value = "article"

    article = scraper.extract("source", "url")

    scraper.extractor.extract.assert_called_once_with("source", "url")
    assert article == "article"