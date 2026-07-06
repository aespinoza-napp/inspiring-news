from src.services.scraper.strategies.playwright import PlaywrightDiscoveryStrategy, PlaywrightExtractionStrategy


def test_extract_dynamic_page(sample_source):

    strategy = PlaywrightExtractionStrategy()

    page = Mock()
    browser = Mock()

    # mock Playwright API

    article = strategy.extract(sample_source, "https://...")

    assert article is not None