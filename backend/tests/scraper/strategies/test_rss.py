from src.services.scraper.strategies.rss import RSSDiscoveryStrategy
from src.config.topics import TOPICS

def test_parse_feed(example_sources):

    strategy = RSSDiscoveryStrategy()
    
    urls = strategy.discover(example_sources, TOPICS)

    assert len(urls) > 0