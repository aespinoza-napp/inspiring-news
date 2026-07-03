from datetime import datetime

import pytest

from src.models.news import News
from src.models.source import NewsSource, SourceType

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
    return [
        NewsSource(
        name="CNN",
        base_url="https://www.cnn.com",
        rss_url="https://rss.cnn.com/rss/edition.rss",
        language="en",
        country="US",
        reliability_index=0.72,
        tags=["general"],
    ),

    NewsSource(
        name="Reuters",
        base_url="https://www.reuters.com",
        language="en",
        country="GB",
        reliability_index=0.96,
        tags=["general", "finance"],
    ),

    NewsSource(
        name="BBC",
        base_url="https://www.bbc.com",
        language="en",
        country="UK",
        reliability_index=0.94,
    ),

    NewsSource(
        name="NASA",
        base_url="https://www.nasa.gov",
        source_type=SourceType.GOVERNMENT,
        reliability_index=1.0,
        tags=["science"],
    )
    ]