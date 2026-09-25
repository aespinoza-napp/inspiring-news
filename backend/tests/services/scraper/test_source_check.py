from datetime import datetime, timezone

from src.models.core.news import News
from src.services.scraper.discovery import DiscoveryResult
from src.services.scraper.request_stats import Outcome, Purpose, RequestStats
from src.services.scraper.source_check import SourceCheckService

from tests.builders.source_builder import build_source


class FakeDiscovery:
    """Canned discovery results per source id."""

    def __init__(self, urls_by_source):
        self.urls_by_source = urls_by_source

    def run(self, source, topics=None):
        found = self.urls_by_source.get(source.id)
        if isinstance(found, Exception):
            raise found
        if not found:
            return DiscoveryResult(tried=["RSSDiscoveryStrategy"], error="HTTP 404")
        return DiscoveryResult(urls=list(found), method="RSSDiscoveryStrategy")


class FakeExtractor:
    """
    Answers per URL, and records into the stats it was given exactly as
    ExtractorService does - which is how the check learns why a page failed.
    """

    def __init__(self, stats, pages):
        self.stats = stats
        self.pages = pages
        self.purposes = []

    def extract(self, source, url, thresholds=None, purpose=Purpose.ARTICLE):

        self.purposes.append(purpose)
        page = self.pages[url]

        if isinstance(page, tuple):
            outcome, status, error = page
            self.stats.record(
                url, outcome, purpose=purpose, source_id=source.id,
                status=status, error=error, tried=["TrafilaturaStrategy"],
            )
            return None

        self.stats.record(
            url, Outcome.OK, purpose=purpose, strategy="TrafilaturaStrategy",
            source_id=source.id, tried=["TrafilaturaStrategy"],
        )
        return page


def article(url, title="A title", author="A. Writer", published=True):

    return News(
        source_id="bbc",
        url=url,
        language="en",
        title=title,
        author=author,
        published_at=datetime(2026, 9, 23, tzinfo=timezone.utc) if published else None,
        content="x" * 500,
    )


def service(urls_by_source, pages, sources=None):

    checker = SourceCheckService(
        sources=sources or [
            build_source(id="bbc", name="BBC"),
            build_source(id="nasa", name="NASA"),
        ],
        discovery=FakeDiscovery(urls_by_source),
        stats=RequestStats(),
    )
    checker.extractor = FakeExtractor(checker.recorder, pages)

    return checker


def by_source(report):
    return {row["source"]: row for row in report["sources"]}


def test_a_source_whose_samples_extract_with_metadata_is_ok():

    urls = ["https://bbc.com/a", "https://bbc.com/b"]

    report = service({"bbc": urls}, {url: article(url) for url in urls}).run(["bbc"])

    [bbc] = report["sources"]
    assert bbc["verdict"] == "ok"
    assert [sample["outcome"] for sample in bbc["samples"]] == ["ok", "ok"]
    assert bbc["samples"][0]["title"] == "A title"
    assert bbc["samples"][0]["strategy"] == "TrafilaturaStrategy"
    assert report["totals"] == {"sources": 1, "ok": 1, "partial": 0, "broken": 0}


def test_a_missing_author_makes_a_source_partial_and_is_named():

    url = "https://bbc.com/a"

    report = service({"bbc": [url]}, {url: article(url, author=None)}).run(["bbc"])

    [bbc] = report["sources"]
    assert bbc["verdict"] == "partial"
    assert bbc["samples"][0]["missing"] == ["author"]


def test_a_failed_extraction_reports_why():

    url = "https://bbc.com/a"

    report = service(
        {"bbc": [url]},
        {url: (Outcome.HTTP_ERROR, 403, "HTTP 403")},
    ).run(["bbc"])

    [bbc] = report["sources"]
    assert bbc["verdict"] == "broken"
    [sample] = bbc["samples"]
    assert (sample["outcome"], sample["status"], sample["error"]) == ("http_error", 403, "HTTP 403")
    # A failed page is broken, not "missing" its metadata.
    assert sample["missing"] == []


def test_a_source_that_discovers_nothing_is_broken_with_the_discovery_error():

    report = service({}, {}).run(["nasa"])

    [nasa] = report["sources"]
    assert nasa["verdict"] == "broken"
    assert nasa["discovery"]["error"] == "HTTP 404"
    assert nasa["samples"] == []


def test_discovery_raising_does_not_take_down_the_other_sources():

    url = "https://bbc.com/a"

    report = service(
        {"bbc": [url], "nasa": RuntimeError("feed exploded")},
        {url: article(url)},
    ).run()

    rows = by_source(report)
    assert rows["bbc"]["verdict"] == "ok"
    assert rows["nasa"]["verdict"] == "broken"
    assert rows["nasa"]["discovery"]["error"] == "feed exploded"


def test_only_per_source_articles_are_fetched():

    urls = [f"https://bbc.com/{n}" for n in range(5)]

    checker = service({"bbc": urls}, {url: article(url) for url in urls})
    report = checker.run(["bbc"], per_source=2)

    assert len(report["sources"][0]["samples"]) == 2
    assert checker.extractor.purposes == [Purpose.SOURCE_CHECK, Purpose.SOURCE_CHECK]


def test_disabled_sources_are_checked_too():

    url = "https://nasa.gov/a"

    report = service(
        {"nasa": [url]},
        {url: article(url)},
        sources=[build_source(id="nasa", name="NASA", enabled=False)],
    ).run()

    [nasa] = report["sources"]
    assert nasa["enabled"] is False
    assert nasa["verdict"] == "ok"


def test_the_checks_fetches_still_reach_the_shared_stats():

    shared = RequestStats()
    url = "https://bbc.com/a"

    checker = SourceCheckService(
        sources=[build_source(id="bbc", name="BBC")],
        discovery=FakeDiscovery({"bbc": [url]}),
        stats=shared,
    )
    checker.extractor = FakeExtractor(checker.recorder, {url: article(url)})

    checker.run()

    [domain] = shared.snapshot()["domains"]
    assert domain["purposes"] == {"source_check": 1}


def test_results_come_back_in_source_order():

    sources = [build_source(id=name, name=name) for name in ("c", "a", "b")]

    report = service({}, {}, sources=sources).run()

    assert [row["source"] for row in report["sources"]] == ["a", "b", "c"]
