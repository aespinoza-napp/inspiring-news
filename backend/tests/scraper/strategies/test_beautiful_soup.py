from src.services.scraper.strategies.beautifulsoup import BeautifulSoupStrategy
from src.database.source_repository import SourceRepository


def test_extract_html():

    strategy = BeautifulSoupStrategy()
    repository = SourceRepository()

    for source in repository.list():

        article = strategy.extract(source, source.url)

        assert article is not None
        assert article.body != ""