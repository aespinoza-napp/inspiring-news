import json
from unittest.mock import Mock, patch

import pytest

from src.config.settings import settings

from src.services.scraper.strategies.trafilatura import TrafilaturaStrategy, _parse_date

from tests.builders.source_builder import build_source


def test_parse_date_returns_none_when_missing():

    assert _parse_date(None) is None
    assert _parse_date("") is None


def test_parse_date_extracts_date_portion():

    assert _parse_date("2024-05-01T10:00:00Z") == "2024-05-01"


def _mock_response(text: str, *, redirect_to: str | None = None) -> Mock:

    response = Mock()
    response.text = text
    response.raise_for_status = Mock()
    # A real Response has this; a bare Mock returns a truthy Mock for it,
    # which the redirect loop reads as "this is a redirect" and follows
    # until it gives up. Fakes have to mirror the attributes the code
    # actually branches on.
    response.is_redirect = redirect_to is not None
    response.headers = {"location": redirect_to} if redirect_to else {}
    return response


@pytest.fixture(autouse=True)
def guard_off(monkeypatch):
    """
    These tests exercise extraction, not the SSRF guard - and leaving it
    on would make them resolve example.com over real DNS. The guard has
    its own suite in tests/scraper/test_url_guard.py.
    """

    monkeypatch.setattr(settings, "URL_GUARD_ENABLED", False)


def test_extract_leaves_published_at_none_when_date_missing():

    payload = json.dumps({"text": "x" * 600, "title": "A title"})

    with patch("src.services.scraper.strategies.trafilatura.requests.get", return_value=_mock_response("<html></html>")), \
         patch("src.services.scraper.strategies.trafilatura.trafilatura.extract", return_value=payload):

        result = TrafilaturaStrategy().extract(build_source(), "https://example.com/a")

    assert result is not None
    assert result.published_at is None


def test_extract_leaves_title_none_when_missing():

    payload = json.dumps({"text": "x" * 600})

    with patch("src.services.scraper.strategies.trafilatura.requests.get", return_value=_mock_response("<html></html>")), \
         patch("src.services.scraper.strategies.trafilatura.trafilatura.extract", return_value=payload):

        result = TrafilaturaStrategy().extract(build_source(), "https://example.com/a")

    assert result is not None
    assert result.title is None


def test_extract_returns_none_on_request_failure():

    with patch(
        "src.services.scraper.strategies.trafilatura.requests.get",
        side_effect=ConnectionError("boom"),
    ):

        result = TrafilaturaStrategy().extract(build_source(), "https://example.com/a")

    assert result is None


# ----------------------------------------------------------------------
# Redirects
#
# requests follows redirects itself, which would walk straight past the
# SSRF guard - a public URL can 302 to 127.0.0.1. Hops are followed here
# instead, one at a time, each re-checked.
# ----------------------------------------------------------------------


def test_a_redirect_is_followed_and_the_destination_is_extracted():

    payload = json.dumps({"text": "x" * 600, "title": "Moved here"})

    responses = [
        _mock_response("", redirect_to="https://example.com/final"),
        _mock_response("<html></html>"),
    ]

    with patch(
        "src.services.scraper.strategies.trafilatura.requests.get",
        side_effect=responses,
    ), patch(
        "src.services.scraper.strategies.trafilatura.trafilatura.extract",
        return_value=payload,
    ):
        result = TrafilaturaStrategy().extract(build_source(), "https://example.com/a")

    assert result is not None
    assert result.title == "Moved here"


def test_every_hop_goes_back_through_the_guard(monkeypatch):
    """
    The whole reason redirects are followed by hand: a public URL that
    302s to a private address must be refused at the second hop.
    """

    from src.services.scraper import url_guard

    monkeypatch.setattr(settings, "URL_GUARD_ENABLED", True)
    monkeypatch.setattr(
        url_guard.socket,
        "getaddrinfo",
        lambda host, port: [
            (2, 1, 6, "", ("127.0.0.1" if host == "internal.example" else "93.184.216.34", 0))
        ],
    )

    responses = [_mock_response("", redirect_to="http://internal.example/admin")]

    with patch(
        "src.services.scraper.strategies.trafilatura.requests.get",
        side_effect=responses,
    ):
        result = TrafilaturaStrategy().extract(build_source(), "https://example.com/a")

    assert result is None


def test_a_redirect_loop_gives_up_rather_than_hanging():

    def always_redirect(url, **kwargs):
        return _mock_response("", redirect_to="https://example.com/loop")

    with patch(
        "src.services.scraper.strategies.trafilatura.requests.get",
        side_effect=always_redirect,
    ):
        result = TrafilaturaStrategy().extract(build_source(), "https://example.com/loop")

    assert result is None
