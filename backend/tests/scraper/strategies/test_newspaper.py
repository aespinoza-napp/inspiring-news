from src.services.scraper.strategies.newspaper import NewspaperStrategy


def test_extract_article(sample_source):

    strategy = NewspaperStrategy()

    article = strategy.extract(sample_source, "https://...")

    assert article is not None