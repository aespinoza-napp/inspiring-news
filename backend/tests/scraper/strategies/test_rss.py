from src.services.scraper.strategies.rss import RSSDiscoveryStrategy


def test_parse_feed(sample_source):

    strategy = RSSDiscoveryStrategy()

    urls = strategy.discover(sample_source)

    assert len(urls) > 0