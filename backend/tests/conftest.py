from datetime import datetime
import tempfile

import pytest


from src.database.qdrant import QdrantDatabase
from src.repositories.vector_repository import VectorRepository
from src.models.news import News
from src.models.source import NewsSource, SourceType
from src.repositories.source_repository import SourceRepository

@pytest.fixture
def example_news():
    return News(
        title="NASA discovers water",
        source_id="cnn",
        url="https://cnn.com/news",
        published_at=datetime.now(),
        content=(
            "NASA discovered water on Mars. "
            "Scientists confirmed the discovery. "
            "A fake image circulated online."
        ),
    )

@pytest.fixture
def example_sources():

    sources = SourceRepository().list()

    return sources


@pytest.fixture
def repository():

    with tempfile.TemporaryDirectory() as path:

        database = QdrantDatabase(
            path=path
        )

        repo = VectorRepository(
            database
        )

        yield repo

        database.client.close()