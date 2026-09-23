from src.models.scraper.extraction import ExtractionResult
from src.services.scraper.extractor import ExtractorService
from src.services.scraper.request_stats import Outcome, Purpose, RequestStats
from src.services.scraper.strategies.base import ExtractionAttempt, ExtractionStrategy

from tests.builders.source_builder import build_source


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
    A real ExtractionStrategy, so the base class's `attempt()` is what
    runs - a Mock would hand back a Mock attempt and test nothing.
    """

    def __init__(self, result=None, attempt=None):
        self.result = result
        self.canned_attempt = attempt
        self.calls = 0

    def extract(self, source, url):
        self.calls += 1
        return self.result

    def attempt(self, source, url):
        if self.canned_attempt is not None:
            self.calls += 1
            return self.canned_attempt
        return super().attempt(source, url)


def make_service(*strategies) -> ExtractorService:

    service = ExtractorService(stats=RequestStats())
    service.strategies = list(strategies)
    return service


def test_first_strategy_success():

    second = StubStrategy()

    service = make_service(StubStrategy(make_extraction_result()), second)

    news = service.extract(build_source(), "https://bbc.com/a")

    assert news is not None
    assert news.title == "A title"

    assert second.calls == 0


def test_fallback_strategy():

    service = make_service(
        StubStrategy(None),
        StubStrategy(make_extraction_result(title="Fallback title")),
    )

    news = service.extract(build_source(), "https://bbc.com/a")

    assert news is not None
    assert news.title == "Fallback title"


def test_skips_strategy_result_that_fails_validation():

    service = make_service(
        StubStrategy(make_extraction_result(body="too short")),
        StubStrategy(make_extraction_result(title="Valid one")),
    )

    news = service.extract(build_source(), "https://bbc.com/a")

    assert news is not None
    assert news.title == "Valid one"


def test_returns_none_when_no_strategy_succeeds():

    service = make_service(StubStrategy(None))

    assert service.extract(build_source(), "https://bbc.com/a") is None


# ----------------------------------------------------------------------
# Every attempt is counted
# ----------------------------------------------------------------------


def _domain(service, domain):

    [entry] = [
        entry
        for entry in service.stats.snapshot()["domains"]
        if entry["domain"] == domain
    ]

    return entry


def test_every_strategy_attempt_is_counted_under_its_domain():

    service = make_service(
        StubStrategy(None),
        StubStrategy(make_extraction_result()),
    )

    service.extract(build_source(), "https://www.bbc.com/a")

    entry = _domain(service, "bbc.com")

    assert entry["requests"] == 2
    assert entry["outcomes"] == {"no_content": 1, "ok": 1}
    assert entry["strategies"] == {"StubStrategy": 2}
    assert entry["sources"] == ["bbc"]


def test_a_body_below_the_minimum_is_counted_as_too_short():
    """
    The strategy did return text; it was the validator that refused it.
    That is a different failure - a paywall or a cookie wall - from a
    page with nothing on it, and it is only visible here.
    """

    service = make_service(StubStrategy(make_extraction_result(body="too short")))

    service.extract(build_source(), "https://bbc.com/a")

    entry = _domain(service, "bbc.com")

    assert entry["outcomes"] == {"too_short": 1}
    assert "too short" in entry["lastError"]


def test_the_purpose_of_the_fetch_is_recorded():

    service = make_service(StubStrategy(make_extraction_result()))

    service.extract(build_source(), "https://bbc.com/a")
    service.extract(build_source(), "https://bbc.com/b", purpose=Purpose.EVIDENCE)

    assert _domain(service, "bbc.com")["purposes"] == {"article": 1, "evidence": 1}


def test_the_status_and_reason_a_strategy_reports_are_kept():

    service = make_service(StubStrategy(attempt=ExtractionAttempt(
        None, Outcome.HTTP_ERROR, status=403, error="HTTP 403",
    )))

    service.extract(build_source(), "https://bbc.com/a")

    entry = _domain(service, "bbc.com")

    assert entry["outcomes"] == {"http_error": 1}
    assert entry["lastStatus"] == 403
    assert entry["lastError"] == "HTTP 403"
