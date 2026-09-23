from src.models.scraper.extraction import ExtractionResult
from src.services.scraper.extractor import ExtractorService
from src.services.scraper.fetcher import FetchedPage
from src.services.scraper.request_stats import Outcome, Purpose, RequestStats
from src.services.scraper.strategies.base import ExtractionAttempt, ExtractionStrategy

from tests.builders.source_builder import build_source

URL = "https://www.bbc.com/a"

PAGE = FetchedPage(url=URL, status=200, html="<html></html>")


def make_extraction_result(**kwargs) -> ExtractionResult:

    defaults = dict(
        source_id="bbc",
        title="A title",
        body="x" * 600,
    )

    defaults.update(kwargs)

    return ExtractionResult(**defaults)


class StubStrategy(ExtractionStrategy):
    """
    A real ExtractionStrategy, so the cascade treats it like one. Records
    the page it was handed, to prove the second parser reads the first
    one's HTML instead of fetching it again.
    """

    def __init__(self, result=None, outcome=None, status=None, reads_html=True, fetches=True):
        self.result = result
        self.outcome = outcome or (Outcome.OK if result else Outcome.NO_CONTENT)
        self.status = status
        self.reads_html = reads_html
        self.fetches = fetches
        self.pages_seen = []

    @property
    def calls(self):
        return len(self.pages_seen)

    def extract(self, source, url):
        return self.result

    def attempt(self, source, url, page=None):
        self.pages_seen.append(page)

        sent = 1 if page is None else 0
        # A failed fetch leaves no page behind for the next parser.
        fetched = page or (PAGE if self.fetches else None)

        return ExtractionAttempt(
            self.result,
            self.outcome,
            self.status,
            error=None if self.result else self.outcome.value,
            page=fetched,
            sent=sent,
        )


def make_service(*strategies) -> ExtractorService:

    service = ExtractorService(stats=RequestStats())
    service.strategies = list(strategies)
    return service


def only_domain(service):

    [entry] = service.stats.snapshot()["domains"]
    return entry


# ----------------------------------------------------------------------
# The cascade
# ----------------------------------------------------------------------


def test_the_first_strategy_that_succeeds_ends_the_cascade():

    second = StubStrategy(make_extraction_result(title="Second"))

    service = make_service(StubStrategy(make_extraction_result()), second)

    news = service.extract(build_source(), URL)

    assert news.title == "A title"
    assert second.calls == 0


def test_a_page_with_no_article_goes_to_the_next_parser_on_the_same_html():
    """
    BeautifulSoup reading the page trafilatura fetched is the whole
    reason the fallback is cheap: one request, two parsers.
    """

    second = StubStrategy(make_extraction_result(title="Fallback title"))

    service = make_service(StubStrategy(None), second)

    news = service.extract(build_source(), URL)

    assert news.title == "Fallback title"
    assert second.pages_seen == [PAGE]
    assert only_domain(service)["requests"] == 1


def test_a_body_below_the_minimum_goes_to_the_next_parser():

    service = make_service(
        StubStrategy(make_extraction_result(body="too short")),
        StubStrategy(make_extraction_result(title="Valid one")),
    )

    assert service.extract(build_source(), URL).title == "Valid one"


def test_a_page_that_is_not_there_ends_the_cascade():
    """No parser can fix a 404; trying one would only spend a request."""

    second = StubStrategy(make_extraction_result())
    browser = StubStrategy(make_extraction_result(), reads_html=False)

    service = make_service(
        StubStrategy(None, Outcome.HTTP_ERROR, status=404, fetches=False),
        second,
        browser,
    )

    assert service.extract(build_source(), URL) is None
    assert second.calls == 0
    assert browser.calls == 0


def test_a_timeout_ends_the_cascade():

    browser = StubStrategy(make_extraction_result(), reads_html=False)

    service = make_service(StubStrategy(None, Outcome.TIMEOUT, fetches=False), browser)

    assert service.extract(build_source(), URL) is None
    assert browser.calls == 0


def test_a_bot_wall_skips_the_other_html_parsers_and_tries_a_browser():
    """
    A 403 comes back the same for any parser that asks with plain HTTP;
    a real browser is the one thing that might get past it.
    """

    second = StubStrategy(make_extraction_result())
    browser = StubStrategy(make_extraction_result(title="Rendered"), reads_html=False)

    service = make_service(
        StubStrategy(None, Outcome.HTTP_ERROR, status=403, fetches=False),
        second,
        browser,
    )

    assert service.extract(build_source(), URL).title == "Rendered"
    assert second.calls == 0
    assert browser.pages_seen == [None]


def test_a_browser_is_never_handed_plain_html():

    browser = StubStrategy(make_extraction_result(), reads_html=False)

    service = make_service(StubStrategy(None), browser)

    service.extract(build_source(), URL)

    assert browser.pages_seen == [None]
    assert only_domain(service)["requests"] == 2


def test_returns_none_when_no_strategy_succeeds():

    service = make_service(StubStrategy(None))

    assert service.extract(build_source(), URL) is None


# ----------------------------------------------------------------------
# What gets counted
# ----------------------------------------------------------------------


def test_one_extraction_is_counted_with_the_strategy_that_won():

    service = make_service(
        StubStrategy(None),
        StubStrategy(make_extraction_result()),
    )

    service.extract(build_source(), URL)

    entry = only_domain(service)

    assert entry["domain"] == "bbc.com"
    assert entry["extractions"] == 1
    assert entry["requests"] == 1
    assert entry["outcomes"] == {"ok": 1}
    assert entry["strategies"] == {"StubStrategy": 1}
    assert entry["tried"] == {"StubStrategy": 2}
    assert entry["sources"] == ["bbc"]


def test_a_body_below_the_minimum_is_counted_as_too_short():
    """
    The strategy did return text; it was the validator that refused it.
    That is a different failure - a paywall or a cookie wall - from a
    page with nothing on it, and it is only visible here.
    """

    service = make_service(StubStrategy(make_extraction_result(body="too short")))

    service.extract(build_source(), URL)

    entry = only_domain(service)

    assert entry["outcomes"] == {"too_short": 1}
    assert "too short" in entry["lastError"]


def test_the_purpose_of_the_fetch_is_recorded():

    service = make_service(StubStrategy(make_extraction_result()))

    service.extract(build_source(), URL)
    service.extract(build_source(), "https://bbc.com/b", purpose=Purpose.EVIDENCE)

    assert only_domain(service)["purposes"] == {"article": 1, "evidence": 1}


def test_the_status_and_reason_of_the_last_attempt_are_kept():

    service = make_service(StubStrategy(None, Outcome.HTTP_ERROR, status=404, fetches=False))

    service.extract(build_source(), URL)

    entry = only_domain(service)

    assert entry["outcomes"] == {"http_error": 1}
    assert entry["lastStatus"] == 404
    assert entry["strategies"] == {}


def test_metadata_the_winning_parser_missed_is_filled_from_the_same_page():
    """
    Trafilatura found the text of an ABC article and no author; the byline
    was in a meta tag the whole time. No second request is made for it.
    """

    page = FetchedPage(
        url=URL,
        status=200,
        html=(
            '<html><head><meta name="author" content="Natalia Soto">'
            '<meta property="article:published_time" content="2026-08-31T09:00:00Z">'
            "</head><body></body></html>"
        ),
    )

    class FoundTextOnly(StubStrategy):
        def attempt(self, source, url, page_=None):
            return ExtractionAttempt(
                make_extraction_result(title="Kept as found"),
                Outcome.OK,
                200,
                page=page,
            )

    news = make_service(FoundTextOnly()).extract(build_source(), URL)

    assert news.title == "Kept as found"
    assert news.author == "Natalia Soto"
    assert str(news.published_at.date()) == "2026-08-31"


def test_evidence_pages_never_reach_the_browser():
    """
    Evidence is fetched by the handful per claim and falls back to its
    search snippet; a render per page would multiply the costliest step.
    """

    browser = StubStrategy(make_extraction_result(), reads_html=False)

    service = make_service(StubStrategy(None), browser)

    assert service.extract(build_source(), URL, purpose=Purpose.EVIDENCE) is None
    assert browser.calls == 0


def test_a_browser_that_is_not_installed_keeps_the_real_reason():
    """
    "unavailable" says nothing about the page; what the HTML parsers
    found is still the answer, with a note saying why nothing more ran.
    """

    service = make_service(
        StubStrategy(None),
        StubStrategy(None, Outcome.UNAVAILABLE, reads_html=False),
    )

    service.extract(build_source(), URL)

    entry = only_domain(service)

    assert entry["outcomes"] == {"no_content": 1}
    assert "not escalated" in entry["lastError"]
