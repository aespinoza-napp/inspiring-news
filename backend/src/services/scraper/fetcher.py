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

from src.services.scraper.url_guard import BlockedURL, check_url

USER_AGENT = "Mozilla/5.0 InspiringNewsBot/1.0"


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

            response = requests.get(
                check_url(url),
                timeout=self.TIMEOUT,
                allow_redirects=False,
                headers={"User-Agent": USER_AGENT},
            )

            if not response.is_redirect:
                response.raise_for_status()
                return FetchedPage(url=url, status=response.status_code, html=response.text)

            url = requests.compat.urljoin(url, response.headers["location"])

        raise BlockedURL(f"Too many redirects starting at {url!r}.")
