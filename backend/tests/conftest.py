from datetime import datetime

import pytest

from src.models.news import News


@pytest.fixture
def example_news():
    return News(
        title="NASA discovers water",
        source="cnn",
        url="https://cnn.com/news",
        published_at=datetime.now(),
        content=(
            "NASA discovered water on Mars. "
            "Scientists confirmed the discovery. "
            "A fake image circulated online."
        ),
    )