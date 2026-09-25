import requests

from src.models.storage.lineage import DataLayer
from src.services.ingestion_service import IngestionService
from src.services.scraper.discovery import DiscoveryResult, DiscoveryService
from src.services.scraper.request_stats import RequestStats
from src.services.scraper.strategies.base import DiscoveryStrategy

from tests.builders.source_builder import build_source


class FakeLake:

    def __init__(self, stored_urls=()):
        self.records = [{"lineage": {"source_url": url}} for url in stored_urls]

    def list(self, layer, limit=None):
        return self.records if layer == DataLayer.RAW else []


class FakeDiscovery:
    """Canned discovery results per source id."""

    def __init__(self, urls_by_source):
        self.urls_by_source = urls_by_source
        self.topics_seen = []

    def run(self, source, topics=None):
        self.topics_seen.append(topics)
        found = self.urls_by_source.get(source.id)
        if isinstance(found, Exception):
            return DiscoveryResult(error=str(found))
        return DiscoveryResult(urls=list(found or []), method="RSSDiscoveryStrategy")


class Jobs:
    """Stands in for the route's _start_job."""

    def __init__(self):
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        return f"job-{len(self.urls)}", False


def service(urls_by_source, stored=(), sources=None):

    return IngestionService(
        sources=sources or [
            build_source(id="bbc", name="BBC"),
            build_source(id="nasa", name="NASA"),
        ],
        lake=FakeLake(stored),
        discovery=FakeDiscovery(urls_by_source),
    )


# ----------------------------------------------------------------------
# IngestionService
# ----------------------------------------------------------------------


def test_new_articles_are_queued_as_analysis_jobs():

    jobs = Jobs()

    report = service({"bbc": ["https://bbc.com/a", "https://bbc.com/b"]}).run(jobs)

    assert jobs.urls == ["https://bbc.com/a", "https://bbc.com/b"]

    [bbc, nasa] = report["sources"]
    assert bbc["queued"] == [
        {"url": "https://bbc.com/a", "jobId": "job-1", "reused": False},
        {"url": "https://bbc.com/b", "jobId": "job-2", "reused": False},
    ]
    assert report["totals"]["queued"] == 2


def test_articles_already_in_the_lake_are_not_analysed_again():
    """Compared by host and path, so a tracking parameter is not a new article."""

    jobs = Jobs()

    report = service(
        {"bbc": ["https://www.bbc.com/a?at_medium=RSS", "https://bbc.com/b"]},
        stored=["https://bbc.com/a/"],
    ).run(jobs)

    assert jobs.urls == ["https://bbc.com/b"]
    assert report["sources"][0]["alreadyStored"] == 1


def test_at_most_per_source_articles_are_queued_and_the_rest_deferred():

    jobs = Jobs()

    report = service({"bbc": [f"https://bbc.com/{n}" for n in range(5)]}).run(jobs, per_source=2)

    assert len(jobs.urls) == 2
    assert report["sources"][0]["deferred"] == 3


def test_an_article_two_sources_syndicate_is_queued_once():

    jobs = Jobs()

    service({
        "bbc": ["https://wire.example.com/story"],
        "nasa": ["https://wire.example.com/story"],
    }).run(jobs)

    assert jobs.urls == ["https://wire.example.com/story"]


def test_only_the_requested_and_enabled_sources_are_read():

    discovery_sources = [
        build_source(id="bbc"),
        build_source(id="nasa"),
        build_source(id="off", enabled=False),
    ]

    ingestion = service({}, sources=discovery_sources)

    assert [source.id for source in ingestion.enabled_sources()] == ["bbc", "nasa"]

    report = ingestion.run(Jobs(), source_ids=["nasa"])

    assert [row["source"] for row in report["sources"]] == ["nasa"]


def test_a_source_whose_discovery_fails_is_reported_not_raised():

    report = service({"bbc": RuntimeError("feed is malformed")}).run(Jobs())

    [bbc, _] = report["sources"]
    assert bbc["discovered"] == 0
    assert "malformed" in bbc["error"]
    assert report["totals"]["failed"] == 1


def test_discovery_asks_for_every_configured_topic():

    from src.config.topics import TOPICS

    ingestion = service({"bbc": []})
    ingestion.run(Jobs())

    assert ingestion.discovery.topics_seen[0] == list(TOPICS)


def test_the_last_run_is_kept_for_the_page():

    ingestion = service({"bbc": ["https://bbc.com/a"]})

    report = ingestion.run(Jobs())

    assert ingestion.last_run is report


# ----------------------------------------------------------------------
# DiscoveryService: cheapest first, and counted
# ----------------------------------------------------------------------


class Canned(DiscoveryStrategy):

    def __init__(self, urls=None, error=None):
        self.urls = urls or []
        self.error = error
        self.calls = 0

    def discover(self, source, topics=None):
        self.calls += 1
        if self.error:
            raise self.error
        return list(self.urls)


def test_the_fallback_is_only_tried_when_the_feed_finds_nothing():

    fallback = Canned(["https://bbc.com/b"])

    discovery = DiscoveryService([Canned(["https://bbc.com/a"]), fallback], stats=RequestStats())

    result = discovery.run(build_source())

    assert result.urls == ["https://bbc.com/a"]
    assert result.method == "Canned"
    assert fallback.calls == 0


def test_a_broken_feed_falls_back_and_both_attempts_are_counted():

    stats = RequestStats()

    error = requests.HTTPError("403", response=type("R", (), {"status_code": 403})())

    discovery = DiscoveryService(
        [Canned(error=error), Canned(["https://bbc.com/a"])],
        stats=stats,
    )

    result = discovery.run(build_source(rss_url="https://bbc.com/rss.xml"))

    assert result.urls == ["https://bbc.com/a"]

    [entry] = stats.snapshot()["domains"]
    assert entry["purposes"] == {"discovery": 2}
    assert entry["outcomes"] == {"http_error": 1, "ok": 1}


def test_topic_pages_are_the_last_discovery_step():
    """Only after both feed steps: they cost one request, it costs up to seven."""

    from src.services.scraper.strategies.rss import RSSDiscoveryStrategy
    from src.services.scraper.strategies.topic_pages import TopicPageDiscoveryStrategy
    from src.services.scraper.strategies.trafilatura_feeds import TrafilaturaFeedDiscoveryStrategy

    assert [type(s) for s in DiscoveryService(stats=RequestStats()).strategies] == [
        RSSDiscoveryStrategy,
        TrafilaturaFeedDiscoveryStrategy,
        TopicPageDiscoveryStrategy,
    ]


def test_when_nothing_is_found_the_reason_is_kept():

    discovery = DiscoveryService([Canned([]), Canned([])], stats=RequestStats())

    result = discovery.run(build_source())

    assert result.urls == []
    assert "no matching article links" in result.error


# ----------------------------------------------------------------------
# TrafilaturaFeedDiscoveryStrategy: URL-only topic filter
# ----------------------------------------------------------------------


def test_trafilatura_discovery_filters_by_article_shape_and_topic(monkeypatch):

    from src.services.scraper.strategies.trafilatura_feeds import TrafilaturaFeedDiscoveryStrategy

    monkeypatch.setattr(
        "src.services.scraper.strategies.trafilatura_feeds.trafilatura.feeds.find_feed_urls",
        lambda url: [
            "https://example.com/science/nasa-launches-telescope",
            "https://example.com/about",
            "https://example.com/videos/science/nasa-clip",
            "https://example.com/sport/football-final",
        ],
    )
    monkeypatch.setattr(
        "src.services.scraper.strategies.trafilatura_feeds.check_url",
        lambda url: url,
    )

    urls = TrafilaturaFeedDiscoveryStrategy().discover(
        build_source(rss_url="https://example.com/rss.xml"),
        topics=["space"],
    )

    assert urls == ["https://example.com/science/nasa-launches-telescope"]


def test_trafilatura_discovery_tries_the_homepage_when_the_feed_is_gone(monkeypatch):
    """Four configured feed URLs had gone 404; the homepages still advertise feeds."""

    from src.services.scraper.strategies.trafilatura_feeds import TrafilaturaFeedDiscoveryStrategy

    asked = []

    def find_feed_urls(url):
        asked.append(url)
        if url.endswith("rss.xml"):
            return []
        return ["https://example.com/2026/09/23/nasa-launches-telescope"]

    monkeypatch.setattr(
        "src.services.scraper.strategies.trafilatura_feeds.trafilatura.feeds.find_feed_urls",
        find_feed_urls,
    )
    monkeypatch.setattr(
        "src.services.scraper.strategies.trafilatura_feeds.check_url",
        lambda url: url,
    )

    urls = TrafilaturaFeedDiscoveryStrategy().discover(
        build_source(base_url="https://example.com", rss_url="https://example.com/rss.xml", language="es"),
        topics=["space"],
    )

    assert asked == ["https://example.com/rss.xml", "https://example.com/"]
    assert urls == ["https://example.com/2026/09/23/nasa-launches-telescope"]
