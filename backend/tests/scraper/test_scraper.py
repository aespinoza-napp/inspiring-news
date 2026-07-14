from pathlib import Path

from src.config.settings import settings
from src.database.local_repository import LocalRepository
from src.database.source_repository import SourceRepository
from src.services.scraper.scraper import Scraper

def test_scraper_pipeline():

    scraper = Scraper()

    storage = LocalRepository(settings.STORAGE_PATH)

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
        print(discovered)
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