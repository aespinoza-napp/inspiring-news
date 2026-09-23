"""
The browser step, against a stand-in for Playwright's sync API - no
package, no Chromium, no network. What is tested is ours: the URL guard
on every request and every redirect hop, the reuse of the HTML parsers,
and how each failure is reported.
"""

import sys
import types

import pytest

from src.config.settings import settings
from src.services.scraper.strategies.playwright_extraction import PlaywrightExtractionStrategy

from tests.builders.source_builder import build_source

URL = "https://example.com/story"

PARAGRAPH = (
    "Hay algo que los jóvenes están haciendo en las plazas de México y "
    "España que los adultos llevamos años sin hacer."
)

RENDERED = (
    '<html><head><meta property="og:title" content="Rendered headline"></head>'
    f"<body><article><p>{PARAGRAPH}</p><p>{PARAGRAPH}</p></article></body></html>"
)


class PlaywrightError(Exception):
    pass


class PlaywrightTimeout(PlaywrightError):
    pass


class FakeRequest:

    def __init__(self, url, resource_type="document", redirected_from=None):
        self.url = url
        self.resource_type = resource_type
        self.redirected_from = redirected_from


class FakeRoute:

    def __init__(self, request):
        self.request = request
        self.decision = None

    def abort(self):
        self.decision = "abort"

    def continue_(self):
        self.decision = "continue"


class FakeBrowser:
    """
    Plays one navigation: the redirect chain, the sub-resources the page
    asks for (each sent through the registered route handler), the status
    and the rendered HTML.
    """

    def __init__(self, scenario):
        self.scenario = scenario
        self.closed = False
        self.routes = []
        self.url = None

    # Browser
    def new_context(self, user_agent=None):
        return self

    def close(self):
        self.closed = True

    # BrowserContext
    def new_page(self):
        return self

    # Page
    def route(self, pattern, handler):
        self.handler = handler

    def goto(self, url, wait_until=None, timeout=None):
        if "raise" in self.scenario:
            raise self.scenario["raise"]

        for sub_url, kind in self.scenario.get("subresources", []):
            route = FakeRoute(FakeRequest(sub_url, kind))
            self.handler(route)
            self.routes.append((sub_url, route.decision))

        request = None
        for hop in self.scenario.get("redirects", [url]):
            request = FakeRequest(hop, redirected_from=request)

        self.url = request.url
        return types.SimpleNamespace(status=self.scenario.get("status", 200), request=request)

    def wait_for_timeout(self, ms):
        pass

    def content(self):
        return self.scenario.get("html", RENDERED)


@pytest.fixture
def playwright(monkeypatch):
    """Installs a fake `playwright.sync_api` and returns its scenario."""

    scenario = {}
    launched = []

    class Chromium:
        def launch(self, headless=True):
            browser = FakeBrowser(scenario)
            launched.append(browser)
            return browser

    class Manager:
        chromium = Chromium()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = lambda: Manager()
    sync_api.Error = PlaywrightError
    sync_api.TimeoutError = PlaywrightTimeout

    package = types.ModuleType("playwright")
    package.sync_api = sync_api

    monkeypatch.setitem(sys.modules, "playwright", package)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)

    # The guard stays on for these tests, with DNS answered here: the
    # point is to prove it is applied, without resolving real hosts.
    monkeypatch.setattr(settings, "URL_GUARD_ENABLED", True)

    def resolve(host, *args, **kwargs):
        address = "127.0.0.1" if host in {"127.0.0.1", "internal.example"} else "93.184.216.34"
        return [(None, None, None, None, (address, 0))]

    monkeypatch.setattr("src.services.scraper.url_guard.socket.getaddrinfo", resolve)

    scenario["launched"] = launched
    return scenario


def attempt():
    return PlaywrightExtractionStrategy().attempt(build_source(), URL)


def test_the_rendered_page_is_read_by_the_same_parsers(playwright):

    result = attempt()

    assert result.outcome == "ok"
    assert result.result.title == "Rendered headline"
    assert result.result.body.startswith("Hay algo")
    assert playwright["launched"][0].closed


def test_without_playwright_installed_it_reports_unavailable(monkeypatch):

    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)

    result = attempt()

    assert result.outcome == "unavailable"
    assert result.sent == 0


def test_without_a_browser_downloaded_it_reports_unavailable(playwright):

    playwright["raise"] = PlaywrightError(
        "BrowserType.launch: Executable doesn't exist at /ms-playwright/chromium"
    )

    assert attempt().outcome == "unavailable"


def test_every_request_the_page_makes_goes_through_the_url_guard(playwright):
    """
    A page can ask the browser for anything. Without this, a rendered
    article could make the server fetch an internal address for it.
    """

    playwright["subresources"] = [
        ("https://cdn.example.com/app.js", "script"),
        ("http://127.0.0.1:6333/collections", "xhr"),
        ("https://cdn.example.com/photo.jpg", "image"),
    ]

    attempt()

    assert playwright["launched"][0].routes == [
        ("https://cdn.example.com/app.js", "continue"),
        ("http://127.0.0.1:6333/collections", "abort"),
        # Images never help find the text; blocked to keep renders cheap.
        ("https://cdn.example.com/photo.jpg", "abort"),
    ]


def test_a_redirect_to_a_forbidden_address_discards_the_page(playwright):

    playwright["redirects"] = [URL, "http://internal.example/admin"]

    result = attempt()

    assert result.outcome == "blocked"
    assert result.result is None


def test_a_forbidden_url_is_refused_before_a_browser_starts(playwright):

    result = PlaywrightExtractionStrategy().attempt(build_source(), "http://127.0.0.1/admin")

    assert result.outcome == "blocked"
    assert playwright["launched"] == []


def test_a_render_that_times_out_is_a_timeout(playwright):

    playwright["raise"] = PlaywrightTimeout("Timeout 30000ms exceeded")

    assert attempt().outcome == "timeout"


def test_a_page_the_browser_cannot_reach_is_a_connection_error(playwright):

    playwright["raise"] = PlaywrightError("page.goto: net::ERR_CONNECTION_REFUSED at https://example.com")

    assert attempt().outcome == "connection_error"


def test_an_error_status_is_reported_with_its_code(playwright):

    playwright["status"] = 403

    result = attempt()

    assert (result.outcome, result.status) == ("http_error", 403)


def test_a_rendered_page_with_no_article_is_no_content(playwright):
    """
    A page with *some* text ("Cargando...") comes back as a result and is
    refused for length by ExtractorService, like any other strategy's.
    Only a page with nothing in it is no_content here.
    """

    playwright["html"] = "<html><body><div id='app'></div></body></html>"

    assert attempt().outcome == "no_content"
