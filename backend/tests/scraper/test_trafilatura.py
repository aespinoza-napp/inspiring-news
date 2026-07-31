import json
from unittest.mock import Mock, patch

from src.models.core.source import NewsSource, SourceType
from src.services.scraper.strategies.trafilatura import TrafilaturaStrategy, _parse_date


def make_source() -> NewsSource:

    return NewsSource(
        id="test",
        name="Test Source",
        base_url="https://example.com",
        source_type=SourceType.NEWS,
    )


def test_parse_date_returns_none_when_missing():

    assert _parse_date(None) is None
    assert _parse_date("") is None


def test_parse_date_extracts_date_portion():

    assert _parse_date("2024-05-01T10:00:00Z") == "2024-05-01"


def _mock_response(text: str) -> Mock:

    response = Mock()
    response.text = text
    response.raise_for_status = Mock()
    return response


def test_extract_leaves_published_at_none_when_date_missing():

    payload = json.dumps({"text": "x" * 600, "title": "A title"})

    with patch("src.services.scraper.strategies.trafilatura.requests.get", return_value=_mock_response("<html></html>")), \
         patch("src.services.scraper.strategies.trafilatura.trafilatura.extract", return_value=payload):

        result = TrafilaturaStrategy().extract(make_source(), "https://example.com/a")

    assert result is not None
    assert result.published_at is None


def test_extract_leaves_title_none_when_missing():

    payload = json.dumps({"text": "x" * 600})

    with patch("src.services.scraper.strategies.trafilatura.requests.get", return_value=_mock_response("<html></html>")), \
         patch("src.services.scraper.strategies.trafilatura.trafilatura.extract", return_value=payload):

        result = TrafilaturaStrategy().extract(make_source(), "https://example.com/a")

    assert result is not None
    assert result.title is None


def test_extract_returns_none_on_request_failure():

    with patch(
        "src.services.scraper.strategies.trafilatura.requests.get",
        side_effect=ConnectionError("boom"),
    ):

        result = TrafilaturaStrategy().extract(make_source(), "https://example.com/a")

    assert result is None
