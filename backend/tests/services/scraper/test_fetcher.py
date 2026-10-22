"""
The one HTTP fetch every HTML parser shares (scraper/fetcher.py): a file
is not a page.

2026-10-22: a PDF decoded as text went down the extraction cascade and
came back as a 167-million-character evidence "page" of binary.
"""

import pytest

from src.services.scraper import fetcher as fetcher_module
from src.services.scraper.fetcher import Fetcher, NotAPage, classify
from src.services.scraper.request_stats import Outcome


class Response:

    def __init__(self, *, content_type="text/html; charset=utf-8", text="<html><p>An article.</p></html>",
                 status=200, location=None):
        self.headers = {"content-type": content_type} if content_type is not None else {}
        if location:
            self.headers["location"] = location
        self.status_code = status
        self.is_redirect = location is not None
        self._text = text
        self.read = False
        self.closed = False

    @property
    def text(self):
        self.read = True
        return self._text

    def raise_for_status(self):
        pass

    def close(self):
        self.closed = True


@pytest.fixture
def served(monkeypatch):
    """requests.get answers with the responses queued, in order; the guard passes every URL."""

    queue = []
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return queue.pop(0)

    monkeypatch.setattr(fetcher_module.requests, "get", get)
    monkeypatch.setattr(fetcher_module, "check_url", lambda url: url)

    return queue, calls


def test_a_page_is_fetched_as_before(served):

    queue, calls = served
    queue.append(Response())

    page = Fetcher().get("https://example.org/a")

    assert page.html == "<html><p>An article.</p></html>"
    assert page.status == 200
    assert calls[0][1]["stream"] is True


@pytest.mark.parametrize("content_type", [
    "application/pdf",
    "application/octet-stream",
    "image/jpeg",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
])
def test_a_file_is_refused_before_its_body_is_read(served, content_type):

    queue, _ = served
    response = Response(content_type=content_type, text="%PDF-1.5 binary")
    queue.append(response)

    with pytest.raises(NotAPage):
        Fetcher().get("https://example.org/report.pdf")

    assert not response.read
    assert response.closed


def test_a_pdf_sent_as_html_is_refused_by_its_first_bytes(served):

    queue, _ = served
    queue.append(Response(content_type="text/html", text="  %PDF-1.5 %\x00\x01 1 0 obj"))

    with pytest.raises(NotAPage):
        Fetcher().get("https://example.org/report")


def test_no_content_type_is_read_as_a_page(served):

    queue, _ = served
    queue.append(Response(content_type=None))

    assert Fetcher().get("https://example.org/a").html.startswith("<html>")


def test_a_redirect_is_followed_and_the_hop_released(served):

    queue, calls = served
    hop = Response(status=301, location="https://example.org/b")
    queue.extend([hop, Response()])

    page = Fetcher().get("https://example.org/a")

    assert [url for url, _ in calls] == ["https://example.org/a", "https://example.org/b"]
    assert page.url == "https://example.org/b"
    assert hop.closed


def test_a_file_counts_as_no_content_not_as_an_error():

    outcome, status, message = classify(NotAPage("https://example.org/r.pdf", 200, "application/pdf"))

    assert outcome == Outcome.NO_CONTENT
    assert status == 200
    assert "application/pdf" in message
