import threading
import time
from logging import getLogger
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup

from src.config.settings import settings
from src.services.concurrency import DUCKDUCKGO
from src.services.scraper.fetcher import USER_AGENT
from src.services.search import SearchUnavailableError

logger = getLogger(__name__)

# The article languages this project has lexicons for, as DuckDuckGo
# regions. A Spanish claim answered from the English-language web
# competes for the same few result slots it was already losing in
# SearXNG before `language` was passed there.
REGIONS = {
    "en": "us-en",
    "es": "es-es",
}

# What the page says when DuckDuckGo decides the request came from a bot:
# HTTP 202 and a "select all squares containing a duck" challenge. Seen on
# every keyless request from the development machine on 2026-09-30 - the
# HTML page by GET and by POST, and the lite page.
CHALLENGE_MARKERS = ("anomaly-modal", "bots use DuckDuckGo too")

# What the page says when the search ran and found nothing.
NO_RESULTS_MARKERS = ('class="no-results"', "No results.")


class DuckDuckGoClient:
    """
    A second search route that needs no API key: DuckDuckGo's HTML
    results page, asked only when SearXNG cannot answer
    (SearxngClient's `fallback`).

    Keyless means scraping a page, with two consequences written down in
    docs/final_document/chapters/09-conclusions/04-future-work/. It refuses by IP: on
    2026-09-25 it CAPTCHA'd every request SearXNG sent it, and on
    2026-09-30 it challenged every direct request too. And the parser
    depends on markup that can change without notice - so a page it does
    not recognise is reported as unavailable, never as "nothing found".
    The parser follows the markup open-source DuckDuckGo clients read
    (`result__a`, `result__snippet`, `uddg=` redirect links); it has been
    tested against sample pages only, because no real results page came
    back from this machine the day it was written.
    """

    # After a challenge, every request is refused here without being sent
    # for this long. A challenged IP asked again is a challenged IP asked
    # again, and each one sent makes the block longer.
    COOLDOWN_SECONDS = 300

    # How its results are tagged in `engines`, so the evaluation can tell
    # which route found a source. Not "duckduckgo", which is SearXNG's
    # own (disabled) engine of that name.
    ENGINE = "duckduckgo-direct"

    def __init__(self, url: str | None = None, timeout: float | None = None):

        self.url = url or settings.DUCKDUCKGO_URL
        self.timeout = timeout or settings.DUCKDUCKGO_TIMEOUT

        self._lock = threading.Lock()
        self._paused_until = 0.0

    def fetch(self, query: str, language: str | None = None) -> list[dict]:
        """
        One query's results, in the shape SearXNG returns them (url,
        title, content, engines); [] when DuckDuckGo searched and found
        nothing; SearchUnavailableError when it could not be asked, would
        not answer, or answered with a page this does not recognise.
        """

        with self._lock:
            remaining = self._paused_until - time.monotonic()

        if remaining > 0:
            raise SearchUnavailableError(
                f"DuckDuckGo paused for {remaining:.0f}s after a bot challenge"
            )

        params = {"q": query}

        region = REGIONS.get(language or "")

        if region:
            params["kl"] = region

        try:
            # Held around this one request only - the same rule as every
            # other permit (src/services/concurrency.py).
            with DUCKDUCKGO.permit():
                response = httpx.get(
                    self.url,
                    params=params,
                    timeout=self.timeout,
                    headers={"User-Agent": USER_AGENT},
                    follow_redirects=True,
                )
        except httpx.HTTPError as exc:
            raise SearchUnavailableError(
                f"DuckDuckGo request failed: {exc or type(exc).__name__}"
            ) from exc

        text = response.text or ""

        if response.status_code in (202, 403, 429) or any(
            marker in text for marker in CHALLENGE_MARKERS
        ):
            self._pause()
            raise SearchUnavailableError(
                f"DuckDuckGo answered with a bot challenge (HTTP {response.status_code}); "
                f"paused for {self.COOLDOWN_SECONDS}s"
            )

        if response.status_code >= 400:
            raise SearchUnavailableError(f"DuckDuckGo answered HTTP {response.status_code}")

        results = parse_results(text)

        if not results and not any(marker in text for marker in NO_RESULTS_MARKERS):
            raise SearchUnavailableError(
                "DuckDuckGo answered with a page that has neither results nor "
                "a no-results notice; its markup may have changed"
            )

        return results

    def _pause(self) -> None:

        with self._lock:
            self._paused_until = time.monotonic() + self.COOLDOWN_SECONDS

        logger.warning(
            "DuckDuckGo challenged the request; not asking it again for %ss",
            self.COOLDOWN_SECONDS,
        )


def parse_results(html: str) -> list[dict]:
    """Every organic result on a DuckDuckGo HTML page, adverts left out."""

    soup = BeautifulSoup(html, "html.parser")

    results = []
    seen = set()

    for block in soup.select("div.result"):

        if "result--ad" in (block.get("class") or []):
            continue

        link = block.select_one("a.result__a")

        if link is None:
            continue

        url = _target(link.get("href") or "")
        title = link.get_text(" ", strip=True)

        if not url or not title or url in seen:
            continue

        seen.add(url)

        snippet = block.select_one(".result__snippet")

        results.append({
            "url": url,
            "title": title,
            "content": snippet.get_text(" ", strip=True) if snippet else "",
            "engines": [DuckDuckGoClient.ENGINE],
        })

    return results


def _target(href: str) -> str:
    """
    The page a result points at. DuckDuckGo links its results through its
    own redirect (`//duckduckgo.com/l/?uddg=<the real URL>`); following
    that would send every evidence fetch through DuckDuckGo first.
    """

    if href.startswith("//"):
        href = f"https:{href}"
    elif href.startswith("/"):
        href = f"https://duckduckgo.com{href}"

    parsed = urlparse(href)

    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        return (parse_qs(parsed.query).get("uddg") or [""])[0]

    return href
