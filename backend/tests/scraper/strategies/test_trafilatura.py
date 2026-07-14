from src.services.scraper.strategies.trafilatura import TrafilaturaStrategy


def test_extract_article(example_sources):

    strategy = TrafilaturaStrategy()

    article = strategy.extract(example_sources, "https://...")

    assert article is not None
    assert article.title