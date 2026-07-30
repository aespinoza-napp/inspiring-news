from pathlib import Path

from src.config.settings import settings
from src.repositories.local_repository import LocalRepository
from src.repositories.source_repository import SourceRepository
from src.services.scraper.scraper import Scraper
from src.models.news import News

def test_scraper_pipeline():

    scraper = Scraper()

    storage = LocalRepository(model=News, folder=settings.RAW_PATH)

    repository = SourceRepository().list()

    discovered = 0
    extracted = 0
    stored = 0
    print(len(repository))
    for source in repository:

        urls = scraper.discover(
            source,
            topics=["space", "technology", "ia"],
        )
        discovered += len(urls)
        for url in urls:

            news = scraper.extract(
                source,
                url,
            )

            if news is None:
                continue

            extracted += 1

            storage.save(news)

            stored += 1

    print()

    print(f"Discovered : {discovered}")
    print(f"Extracted  : {extracted}")
    print(f"Stored     : {stored}")

    assert stored > 0

test_scraper_pipeline()