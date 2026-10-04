"""
Time from publication to reception: the times discovery and extraction
now keep, the sightings ingestion records, and the freshness report that
joins them with the lake. Lags are checked against values worked out by
hand. Nothing here touches the real lake (invariant 9).
"""

from datetime import datetime, timedelta, timezone

import feedparser
import pytest

from src.models.storage.lineage import DataLayer
from src.services.freshness import freshness
from src.services.ingestion_service import IngestionService
from src.services.scraper.discovery import DiscoveryResult, DiscoveryService
from src.services.scraper.fetcher import FetchedPage, Fetcher
from src.services.scraper.request_stats import Purpose, RequestStats
from src.services.scraper.sightings import Sightings
from src.services.scraper.strategies.beautifulsoup import _timestamp
from src.services.scraper.strategies.rss import RSSDiscoveryStrategy

from tests.builders.source_builder import build_source
from tests.services.scraper.test_extractor import PAGE, StubStrategy, make_extraction_result, make_service

UTC = timezone.utc


def at(hour: int, minute: int = 0, day: int = 4) -> datetime:

    return datetime(2026, 10, day, hour, minute, tzinfo=UTC)


# ----------------------------------------------------------------------
# Discovery keeps the feed's time
# ----------------------------------------------------------------------


class FakeFeed:

    def __init__(self, entries):
        self.entries = entries


def test_the_rss_strategy_keeps_each_items_publication_time(monkeypatch):

    monkeypatch.setattr(Fetcher, "get", lambda self, url: FetchedPage(url=url, status=200, html="<rss/>"))

    entries = [
        feedparser.FeedParserDict(
            link="https://example.com/science/a-long-headline-about-reefs",
            title="Reefs", published_parsed=(2026, 10, 4, 7, 30, 0, 6, 277, 0),
        ),
        feedparser.FeedParserDict(
            link="https://example.com/science/another-long-headline-here",
            title="Another", updated_parsed=(2026, 10, 3, 22, 5, 0, 5, 276, 0),
        ),
        feedparser.FeedParserDict(
            link="https://example.com/science/no-date-at-all-in-this-one", title="Undated",
        ),
    ]

    monkeypatch.setattr(feedparser, "parse", lambda html: FakeFeed(entries))

    source = build_source(rss_url="https://example.com/rss.xml", language="es")

    result = DiscoveryService(strategies=[RSSDiscoveryStrategy()], stats=RequestStats()).run(source)

    assert result.published == {
        "https://example.com/science/a-long-headline-about-reefs": at(7, 30),
        "https://example.com/science/another-long-headline-here": at(22, 5, day=3),
    }
    assert len(result.urls) == 3


def test_a_strategy_that_knows_no_times_still_discovers():

    class Plain:
        def discover(self, source, topics):
            return ["https://example.com/a"]

    result = DiscoveryService(strategies=[Plain()], stats=RequestStats()).run(build_source())

    assert (result.urls, result.published) == (["https://example.com/a"], {})


# ----------------------------------------------------------------------
# Extraction keeps the page's time, for stored articles only
# ----------------------------------------------------------------------


@pytest.mark.parametrize("value, expected", [
    ("2026-10-04T08:15:00+02:00", datetime(2026, 10, 4, 8, 15, tzinfo=timezone(timedelta(hours=2)))),
    ("2026-10-04T06:15:00Z", at(6, 15)),
    ("2026-10-04 06:15", datetime(2026, 10, 4, 6, 15)),
    ("2026-10-04", None),                       # a date is not a time
    ("2026-10-04T00:00:00+00:00", None),        # "midnight" is how a date-only site writes it
    ("4 October 2026", None),
    (None, None),
])
def test_only_a_stated_time_of_day_is_a_publication_time(value, expected):

    assert _timestamp(value) == expected


HTML_WITH_TIME = (
    '<html><head><meta property="article:published_time" content="2026-10-04T06:15:00Z">'
    "</head><body><p>text</p></body></html>"
)


@pytest.mark.parametrize("purpose, expected", [
    (Purpose.ARTICLE, {"publishedTime": "2026-10-04T06:15:00+00:00"}),
    (Purpose.INGESTION, {"publishedTime": "2026-10-04T06:15:00+00:00"}),
    (Purpose.EVIDENCE, {}),   # dozens per claim, never stored: not worth a parse
])
def test_a_stored_article_keeps_the_pages_time_in_its_metadata(purpose, expected):

    page = FetchedPage(url=PAGE.url, status=200, html=HTML_WITH_TIME)

    class OnThisPage(StubStrategy):
        def attempt(self, source, url, page_=None):
            attempt = super().attempt(source, url, page_)
            attempt.page = page
            return attempt

    winner = OnThisPage(make_extraction_result(author="A", published_at="2026-10-04", summary="s", lead_image="i"))

    news = make_service(winner).extract(build_source(id="bbc"), PAGE.url, purpose=purpose)

    assert news.metadata == expected


# ----------------------------------------------------------------------
# Sightings
# ----------------------------------------------------------------------


def test_the_first_sighting_is_kept_and_a_later_one_only_adds_a_feed_time(tmp_path):

    path = tmp_path / "sightings.json"
    store = Sightings(path)

    assert store.record(["https://www.bbc.com/a?at_medium=RSS"], source_id="bbc", method="RSS", seen_at=at(9)) == 1

    assert store.record(
        ["https://bbc.com/a/"], source_id="bbc", method="RSS",
        published={"https://bbc.com/a/": at(7)}, seen_at=at(12),
    ) == 0

    [entry] = Sightings(path).all().values()   # read back from disk

    assert entry["firstSeenAt"] == "2026-10-04T09:00:00+00:00"
    assert entry["feedPublishedAt"] == "2026-10-04T07:00:00+00:00"


def test_ingestion_records_new_articles_with_their_feed_time_and_not_stored_ones():

    class Lake:
        def list(self, layer, limit=None):
            return [{"lineage": {"source_url": "https://bbc.com/old"}}] if layer == DataLayer.RAW else []

    class Discovery:
        def run(self, source, topics=None):
            return DiscoveryResult(
                urls=["https://bbc.com/old", "https://bbc.com/new", "https://bbc.com/later"],
                method="RSSDiscoveryStrategy",
                published={"https://bbc.com/new": at(6)},
            )

    store = Sightings()

    IngestionService([build_source(id="bbc")], Lake(), Discovery(), sightings=store).run(
        lambda url: ("job", False), per_source=1,
    )

    entries = store.all()

    # The deferred one is seen too: its wait for a later run is real delay.
    assert sorted(entries) == ["bbc.com/later", "bbc.com/new"]
    assert entries["bbc.com/new"]["feedPublishedAt"] == "2026-10-04T06:00:00+00:00"
    assert entries["bbc.com/new"]["method"] == "RSSDiscoveryStrategy"


# ----------------------------------------------------------------------
# The report
# ----------------------------------------------------------------------


class Lake:

    def __init__(self, raw=(), processed=(), exploitation=()):
        self.layers = {
            DataLayer.RAW: list(raw),
            DataLayer.PROCESSED: list(processed),
            DataLayer.EXPLOITATION: list(exploitation),
        }

    def list(self, layer, limit=None):
        return self.layers[layer]


def raw(url, fetched, *, source="bbc", date=None, page_time=None):

    return {
        "lineage": {"source_url": url, "produced_at": fetched.isoformat()},
        "fetched_at": fetched.isoformat(),
        "article": {
            "url": url, "source_id": source, "title": "T", "published_at": date,
            "metadata": {"publishedTime": page_time} if page_time else {},
        },
    }


def produced(url, when, publishable=None):

    record = {"lineage": {"source_url": url, "produced_at": when.isoformat()}}

    if publishable is not None:
        record["publishable"] = publishable

    return record


def test_the_lags_against_times_worked_out_by_hand():
    """
    Published 06:00 (feed), seen 09:00, fetched 09:30, analysed 09:33,
    on the reader 09:34: seen 3 h, queue 0.5 h, reception 3.5 h,
    processing 0.05 h, available 3.5667 h.
    """

    url = "https://bbc.com/a"

    lake = Lake(
        raw=[raw(url, at(9, 30)), raw(url + "?again=1", at(15))],   # a later re-analysis
        processed=[produced(url, at(9, 33))],
        exploitation=[produced(url, at(9, 34), publishable=True)],
    )

    sightings = {"bbc.com/a": {"firstSeenAt": at(9).isoformat(), "feedPublishedAt": at(6).isoformat()}}

    report = freshness(lake, sightings)

    [row] = report["articles"]

    assert row["publishedFrom"] == "feed"
    assert row["via"] == "ingestion"
    assert row["lagHours"] == {"seen": 3.0, "queue": 0.5, "reception": 3.5, "processing": 0.05, "available": 3.57}
    assert row["fetchedAt"] == "2026-10-04T09:30:00+00:00"   # the first reception, not the re-analysis

    totals = report["totals"]
    assert totals["hours"]["reception"] == {"n": 1, "median": 3.5, "p90": 3.5, "negative": 0}
    assert totals["publishable"] == 1


def test_without_a_feed_time_the_pages_time_is_used_and_a_date_alone_counts_in_days():

    lake = Lake(raw=[
        raw("https://nasa.gov/x", at(12), source="nasa", page_time="2026-10-04T10:00:00+00:00", date="2026-10-04"),
        raw("https://nasa.gov/y", at(12), source="nasa", date="2026-10-02"),
        raw("https://nasa.gov/z", at(12), source="nasa"),
    ])

    report = freshness(lake, {})

    rows = {row["url"]: row for row in report["articles"]}

    assert rows["https://nasa.gov/x"]["publishedFrom"] == "page"
    assert rows["https://nasa.gov/x"]["lagHours"]["reception"] == 2.0
    assert rows["https://nasa.gov/x"]["via"] == "posted"

    # Only a date: no hours invented, the difference in days instead.
    assert rows["https://nasa.gov/y"]["publishedFrom"] == "date"
    assert rows["https://nasa.gov/y"]["lagHours"]["reception"] is None
    assert rows["https://nasa.gov/y"]["receptionDays"] == 2

    assert rows["https://nasa.gov/z"]["publishedFrom"] is None

    [nasa] = report["sources"]
    assert nasa["publishedFrom"] == {"feed": 0, "page": 1, "date": 1, "none": 1}
    assert nasa["receptionDays"]["median"] == 2.0


def test_a_publication_after_we_fetched_it_is_counted_not_averaged():

    lake = Lake(raw=[
        raw("https://bbc.com/a", at(9)),
        raw("https://bbc.com/b", at(9)),
    ])

    sightings = {
        "bbc.com/a": {"firstSeenAt": at(8).isoformat(), "feedPublishedAt": at(10).isoformat()},
        "bbc.com/b": {"firstSeenAt": at(8).isoformat(), "feedPublishedAt": at(5).isoformat()},
    }

    reception = freshness(lake, sightings)["totals"]["hours"]["reception"]

    assert reception == {"n": 1, "median": 4.0, "p90": 4.0, "negative": 1}


def test_a_naive_page_time_is_flagged():

    lake = Lake(raw=[raw("https://bbc.com/a", at(9), page_time="2026-10-04T07:00:00")])

    [row] = freshness(lake, {})["articles"]

    assert row["noTimezone"] is True


def test_an_empty_lake_is_an_empty_report():

    report = freshness(Lake(), {})

    assert report["articles"] == [] and report["sources"] == []
    assert report["totals"]["hours"]["reception"]["median"] is None


def test_the_lakes_naive_local_times_are_compared_with_utc_feed_times():
    """The lake writes datetime.now() - naive, this machine's local time."""

    fetched_local = at(9, 30).astimezone().replace(tzinfo=None)

    lake = Lake(raw=[raw("https://bbc.com/a", fetched_local)])

    sightings = {"bbc.com/a": {"firstSeenAt": at(9).isoformat(), "feedPublishedAt": at(6).isoformat()}}

    [row] = freshness(lake, sightings)["articles"]

    assert row["lagHours"]["reception"] == 3.5
