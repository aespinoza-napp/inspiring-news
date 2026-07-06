from unittest.mock import Mock

from src.services.scraper.discovery import DiscoveryService


def test_returns_first_success():

    service = DiscoveryService()

    rss = Mock()
    rss.discover.return_value = ["a", "b"]

    playwright = Mock()

    service.strategies = [rss, playwright]

    urls = service.discover("source")

    assert urls == ["a", "b"]
    playwright.discover.assert_not_called()


def test_fallback_to_second_strategy():

    service = DiscoveryService()

    rss = Mock()
    rss.discover.return_value = []

    playwright = Mock()
    playwright.discover.return_value = ["url"]

    service.strategies = [rss, playwright]

    urls = service.discover("source")

    assert urls == ["url"]