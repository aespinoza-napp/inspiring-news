"""
One HTTP fetch, shared by every parser that reads the same page.

Trafilatura and BeautifulSoup both work from HTML, and the cascade tries
the second only when the first finds no article. Fetching again for the
second parser would double the requests sent to exactly the sources that
are already hardest to scrape - so the page is fetched once and handed
down the cascade. Only a strategy that needs something plain HTML cannot
give it (a rendered DOM, for Playwright) goes back to the network.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

from src.services.scraper.request_stats import Outcome
from src.services.scraper.url_guard import BlockedURL, UnresolvableHost, check_url

USER_AGENT = "Mozilla/5.0 InspiringNewsBot/1.0"

# Content types no parser here can read. A PDF decoded as text went down
# the cascade on 2026-10-22 and BeautifulSoup returned its bytes as the
# article: 167 million characters of "%PDF-1.5 ..." became an evidence
# page for two train claims, ranked on its first 2,000 characters and
# searched for passages to show the verifier. Refused before the body is
# read, so a 50 MB report is not downloaded to be thrown away.
NOT_PAGES = (
    "application/pdf",
    "application/octet-stream",
    "application/zip",
    "application/msword",
    "application/vnd.",
    "image/",
    "audio/",
    "video/",
    "font/",
)

# A server that labels a PDF as HTML still sends a PDF.
PDF_MAGIC = "%PDF-"


class NotAPage(Exception):
    """The URL answered with a file, not a page: nothing to extract."""

    def __init__(self, url: str, status: int, what: str):
        super().__init__(f"not a web page ({what}): {url}")
        self.status = status


@dataclass(frozen=True)
class FetchedPage:
    """A page as the server returned it, after any redirects."""

    url: str

    status: int

    html: str


class Fetcher:

    TIMEOUT = 20

    # requests follows redirects itself, which would walk straight past
    # the guard - a public URL can 302 to 127.0.0.1. Hops are followed
    # here instead, one at a time, re-checking each.
    MAX_REDIRECTS = 5

    def get(self, url: str) -> FetchedPage:
        """
        Raises BlockedURL (or its UnresolvableHost subclass),
        requests.HTTPError for a 4xx/5xx, and requests' own Timeout and
        ConnectionError - the strategies turn each into an Outcome.
        """

        for _ in range(self.MAX_REDIRECTS + 1):

            # Streamed, so the headers can refuse a file before its body
            # is read; a page's body is read whole by `.text` below.
            response = requests.get(
                check_url(url),
                timeout=self.TIMEOUT,
                allow_redirects=False,
                headers={"User-Agent": USER_AGENT},
                stream=True,
            )

            if not response.is_redirect:

                response.raise_for_status()

                kind = (response.headers.get("content-type") or "").split(";")[0].strip().lower()

                if kind.startswith(NOT_PAGES):
                    response.close()
                    raise NotAPage(url, response.status_code, kind)

                html = response.text

                if html.lstrip()[:len(PDF_MAGIC)] == PDF_MAGIC:
                    raise NotAPage(url, response.status_code, "a PDF")

                return FetchedPage(url=url, status=response.status_code, html=html)

            response.close()

            url = requests.compat.urljoin(url, response.headers["location"])

        raise BlockedURL(f"Too many redirects starting at {url!r}.")


def classify(exc: Exception) -> tuple[Outcome, int | None, str]:
    """
    What a failed fetch came to, as (outcome, HTTP status, message).
    Shared by extraction and discovery so a 403 on a feed and a 403 on an
    article are counted the same way.
    """

    if isinstance(exc, UnresolvableHost):
        return Outcome.CONNECTION_ERROR, None, str(exc)

    if isinstance(exc, BlockedURL):
        return Outcome.BLOCKED, None, str(exc)

    # Fetched, and nothing in it a parser could read as an article.
    if isinstance(exc, NotAPage):
        return Outcome.NO_CONTENT, exc.status, str(exc)

    if isinstance(exc, requests.HTTPError):
        status = exc.response.status_code if exc.response is not None else None
        return Outcome.HTTP_ERROR, status, f"HTTP {status}"

    if isinstance(exc, requests.Timeout):
        return Outcome.TIMEOUT, None, str(exc)

    if isinstance(exc, requests.ConnectionError):
        return Outcome.CONNECTION_ERROR, None, str(exc)

    return Outcome.ERROR, None, str(exc)
