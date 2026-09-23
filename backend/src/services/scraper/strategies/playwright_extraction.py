"""
The last and most expensive step of the extraction cascade: render the
page in a headless browser, then read the result with the same parsers
the cheap steps use.

A page reaches this only when trafilatura and BeautifulSoup both found
no article in the plain HTML (usually a page that builds its text with
JavaScript), or when the server refused plain HTTP with a 401/403/429
that a real browser can sometimes get past. It never runs for a 404, a
timeout or a host that does not resolve - see `ExtractorService`.

It only *renders*. The rendered HTML goes through TrafilaturaStrategy and
then BeautifulSoupStrategy's `parse()`, so there is one notion of "where
the article is" in the codebase, not a third one written against the
Playwright API.

Optional: `playwright` is an extra (`uv sync --extra browser`, then
`uv run playwright install chromium`). Without it, or without a browser
downloaded, every attempt reports `unavailable` and the cascade keeps
the previous step's result.
"""

from __future__ import annotations

from logging import getLogger
from urllib.parse import urlsplit

from src.models.core.source import NewsSource
from src.models.scraper.extraction import ExtractionResult
from src.services.concurrency import BROWSER
from src.services.scraper.fetcher import FetchedPage, USER_AGENT
from src.services.scraper.request_stats import Outcome
from src.services.scraper.url_guard import BlockedURL, UnresolvableHost, check_url

from .base import ExtractionAttempt, ExtractionStrategy
from .beautifulsoup import BeautifulSoupStrategy
from .trafilatura import TrafilaturaStrategy

logger = getLogger(__name__)

# Sub-resources the text never depends on. Blocking them is most of what
# makes a render affordable.
SKIPPED_RESOURCES = {"image", "font", "media"}

NAVIGATION_TIMEOUT_MS = 30_000

# How long to let late scripts fill the page in after it has loaded.
# "networkidle" would be more thorough and, on ad-heavy news sites,
# frequently never arrives.
SETTLE_MS = 1_500


class PlaywrightExtractionStrategy(ExtractionStrategy):

    # Renders its own page; handing it plain HTML would defeat the point.
    reads_html = False

    def __init__(self):

        self.parsers = [TrafilaturaStrategy(), BeautifulSoupStrategy()]

    def extract(
        self,
        source: NewsSource,
        url: str,
    ) -> ExtractionResult | None:

        return self.attempt(source, url).result

    def attempt(
        self,
        source: NewsSource,
        url: str,
        page: FetchedPage | None = None,
    ) -> ExtractionAttempt:

        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import TimeoutError as PlaywrightTimeout
            from playwright.sync_api import sync_playwright
        except ImportError:
            return ExtractionAttempt(
                None,
                Outcome.UNAVAILABLE,
                error="playwright is not installed (uv sync --extra browser)",
                sent=0,
            )

        try:
            check_url(url)
        except UnresolvableHost as exc:
            return ExtractionAttempt(None, Outcome.CONNECTION_ERROR, error=str(exc), sent=0)
        except BlockedURL as exc:
            return ExtractionAttempt(None, Outcome.BLOCKED, error=str(exc), sent=0)

        try:
            with BROWSER.permit():
                rendered = self._render(sync_playwright, url)

        except PlaywrightTimeout as exc:
            logger.warning("Timed out rendering %s: %s", url, exc)
            return ExtractionAttempt(None, Outcome.TIMEOUT, error="render timed out")

        except BlockedURL as exc:
            logger.warning("Refused a redirect while rendering %s: %s", url, exc)
            return ExtractionAttempt(None, Outcome.BLOCKED, error=str(exc))

        except PlaywrightError as exc:
            message = str(exc)

            # A browser that was never downloaded is not the page's fault.
            if "Executable doesn't exist" in message or "playwright install" in message:
                return ExtractionAttempt(
                    None,
                    Outcome.UNAVAILABLE,
                    error="no browser installed (uv run playwright install chromium)",
                    sent=0,
                )

            outcome = (
                Outcome.CONNECTION_ERROR
                if "net::ERR_" in message
                else Outcome.ERROR
            )
            logger.warning("Could not render %s: %s", url, message.splitlines()[0])
            return ExtractionAttempt(None, outcome, error=message.splitlines()[0])

        if rendered.status >= 400:
            return ExtractionAttempt(
                None, Outcome.HTTP_ERROR, rendered.status, f"HTTP {rendered.status}"
            )

        # The same parsers as the cheap steps, on the rendered DOM.
        for parser in self.parsers:

            result = parser.parse(source, rendered)

            if result is not None and result.body.strip():
                return ExtractionAttempt(result, Outcome.OK, rendered.status, page=rendered)

        return ExtractionAttempt(None, Outcome.NO_CONTENT, rendered.status, page=rendered)

    def _render(self, sync_playwright, url: str) -> FetchedPage:
        """
        One browser per render. Playwright's sync objects belong to the
        thread that made them, and extraction runs on many threads, so a
        shared browser is not an option without a dedicated thread of its
        own - worth doing if renders become common, not before.
        """

        allowed: dict[str, bool] = {}

        def guard(route):
            """
            Every request the page makes goes through the URL guard, not
            only the first. A page can ask the browser for anything - an
            internal admin panel included - and the browser would fetch
            it on our behalf. Decisions are cached per host: a news page
            makes a hundred requests to a dozen hosts.
            """

            request = route.request

            if request.resource_type in SKIPPED_RESOURCES:
                return route.abort()

            host = urlsplit(request.url).netloc

            if host not in allowed:
                try:
                    check_url(request.url)
                    allowed[host] = True
                except BlockedURL:
                    allowed[host] = False

            return route.continue_() if allowed[host] else route.abort()

        with sync_playwright() as playwright:

            browser = playwright.chromium.launch(headless=True)

            try:
                context = browser.new_context(user_agent=USER_AGENT)
                page = context.new_page()
                page.route("**/*", guard)

                response = page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=NAVIGATION_TIMEOUT_MS,
                )

                # Route handlers do not see the hops of a redirected
                # navigation, so the chain is checked afterwards: content
                # that arrived by way of a forbidden address is discarded.
                request = response.request if response else None

                while request is not None:
                    check_url(request.url)
                    request = request.redirected_from

                page.wait_for_timeout(SETTLE_MS)

                return FetchedPage(
                    url=page.url,
                    status=response.status if response else 0,
                    html=page.content(),
                )

            finally:
                browser.close()
