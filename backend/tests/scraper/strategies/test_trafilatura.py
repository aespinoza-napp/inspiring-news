from src.services.scraper.strategies.trafilatura import TrafilaturaStrategy


def test_extract_article(sample_source):

    strategy = TrafilaturaStrategy()

    article = strategy.extract(sample_source, "https://...")

    assert article is not None
    assert article.title