from unittest.mock import Mock

from src.services.scraper.extractor import ExtractorService


def test_first_strategy_success():

    service = ExtractorService()

    trafilatura = Mock()
    trafilatura.extract.return_value = "news"

    newspaper = Mock()

    service.strategies = [trafilatura, newspaper]

    article = service.extract("source", "url")

    assert article == "news"

    newspaper.extract.assert_not_called()


def test_fallback_strategy():

    service = ExtractorService()

    trafilatura = Mock()
    trafilatura.extract.return_value = None

    newspaper = Mock()
    newspaper.extract.return_value = "news"

    service.strategies = [trafilatura, newspaper]

    article = service.extract("source", "url")

    assert article == "news"