from datetime import datetime

import pytest

from src.models.fact_checker.fact_check import Verdict
from src.models.storage.lineage import DataLayer
from src.services.reader.index import ReaderIndex
from src.services.reader.views import reader_id

from tests.services.reader.reader_lake import (
    SCRAPED_BODY,
    CountingLake,
    checked,
    make_lake,
    publish,
    restamp,
)


@pytest.fixture
def lake(tmp_path):

    return make_lake(tmp_path)


# ----------------------------------------------------------------------
# What the feed holds
# ----------------------------------------------------------------------


def test_an_empty_lake_is_an_empty_feed_that_says_nothing_was_analysed(lake):

    feed = ReaderIndex(lake).feed()

    assert feed["items"] == []
    assert feed["total"] == 0
    assert feed["lake"] == {"analysed": 0, "publishable": 0}


def test_only_publishable_articles_are_listed(lake):

    publish(lake, "https://a.example/kept-in-the-feed-story")
    publish(lake, "https://a.example/judged-false-story-here", verdict=Verdict.FALSE)
    publish(lake, "https://a.example/rejected-at-admission-story", validation_passed=False)

    feed = ReaderIndex(lake).feed()

    assert [item["url"] for item in feed["items"]] == ["https://a.example/kept-in-the-feed-story"]
    # The empty-state wording depends on telling these two apart.
    assert feed["lake"] == {"analysed": 3, "publishable": 1}


def test_newest_first_by_publication_date_or_else_by_when_it_was_checked(lake):

    publish(lake, "https://a.example/older-published-story", published_at=datetime(2026, 8, 1))
    publish(lake, "https://a.example/newer-published-story", published_at=datetime(2026, 9, 1))
    undated = publish(lake, "https://a.example/story-with-no-date", published_at=None)

    restamp(lake, undated.exploitation_record_id, "2026-08-15T09:00:00")

    urls = [item["url"] for item in ReaderIndex(lake).feed()["items"]]

    assert urls == [
        "https://a.example/newer-published-story",
        "https://a.example/story-with-no-date",
        "https://a.example/older-published-story",
    ]


def test_the_newest_run_of_an_article_decides_whether_it_is_published(lake):
    """
    Re-analysed and now FALSE: the article leaves the feed, whatever an
    earlier run decided. Compared by host and path, so a tracking
    parameter does not make the re-run a different article.
    """

    first = publish(lake, "https://a.example/re-checked-story")
    second = publish(lake, "https://www.a.example/re-checked-story/?utm_source=x", verdict=Verdict.FALSE)

    restamp(lake, first.exploitation_record_id, "2026-09-01T10:00:00")
    restamp(lake, second.exploitation_record_id, "2026-09-02T10:00:00")

    index = ReaderIndex(lake)

    assert index.feed()["items"] == []
    assert index.article(reader_id("https://a.example/re-checked-story")) is None


def test_a_re_run_that_publishes_replaces_the_older_card(lake):

    first = publish(lake, "https://a.example/re-checked-story", title="First title")
    second = publish(lake, "https://a.example/re-checked-story", title="Second title")

    restamp(lake, first.exploitation_record_id, "2026-09-01T10:00:00")
    restamp(lake, second.exploitation_record_id, "2026-09-02T10:00:00")

    items = ReaderIndex(lake).feed()["items"]

    assert [item["headline"] for item in items] == ["Second title"]


# ----------------------------------------------------------------------
# Filters, facets, pages
# ----------------------------------------------------------------------


def test_topic_and_language_filter_and_each_facet_counts_under_the_other(lake):

    publish(lake, "https://a.example/one-english-climate-story", topic="Climate", language="en")
    publish(lake, "https://a.example/two-spanish-climate-story", topic="Climate", language="es")
    publish(lake, "https://a.example/three-spanish-health-story", topic="Health", language="es")

    index = ReaderIndex(lake)

    spanish = index.feed(language="es")
    assert spanish["total"] == 2
    assert spanish["topics"] == [{"topic": "Climate", "count": 1}, {"topic": "Health", "count": 1}]

    # Case-insensitive: the topic arrives from a URL.
    climate = index.feed(topic="climate")
    assert climate["total"] == 2
    assert climate["languages"] == [{"language": "en", "count": 1}, {"language": "es", "count": 1}]

    both = index.feed(topic="Climate", language="es")
    assert [item["url"] for item in both["items"]] == ["https://a.example/two-spanish-climate-story"]


def test_pages_are_offset_and_limit_over_the_filtered_list(lake):

    for day in range(1, 6):
        publish(lake, f"https://a.example/story-number-{day}-of-five", published_at=datetime(2026, 9, day))

    page = ReaderIndex(lake).feed(offset=1, limit=2)

    assert page["total"] == 5
    assert [item["url"] for item in page["items"]] == [
        "https://a.example/story-number-4-of-five",
        "https://a.example/story-number-3-of-five",
    ]


# ----------------------------------------------------------------------
# What a request costs
# ----------------------------------------------------------------------


def test_an_unchanged_lake_costs_no_reads(lake):
    """
    /scraper/articles re-reads the whole lake on every poll. The feed must
    not: with the stamps unchanged, a second request opens no record.
    """

    publish(lake)

    counting = CountingLake(lake)
    index = ReaderIndex(counting)

    index.feed()
    first = dict(counting.reads)

    index.feed()
    index.feed(topic="Environment")

    assert dict(counting.reads) == first
    assert first[DataLayer.PROCESSED] == 1


def test_a_new_analysis_costs_reading_that_analysis_only(lake):

    publish(lake, "https://a.example/first-story-in-the-lake")
    publish(lake, "https://a.example/second-story-in-the-lake")

    counting = CountingLake(lake)
    index = ReaderIndex(counting)
    index.feed()

    counting.reads.clear()

    publish(lake, "https://a.example/third-story-in-the-lake")

    assert index.feed()["total"] == 3
    assert counting.reads[DataLayer.EXPLOITATION] == 1
    assert counting.reads[DataLayer.PROCESSED] == 1


def test_a_rejected_article_never_costs_a_read_of_its_processed_record(lake):
    """The feed does not show it, so its heavy record is never opened."""

    publish(lake, validation_passed=False)

    counting = CountingLake(lake)
    ReaderIndex(counting).feed()

    assert counting.reads[DataLayer.PROCESSED] == 0


def test_a_removed_record_leaves_the_feed(lake, tmp_path):

    written = publish(lake)

    index = ReaderIndex(lake)
    assert index.feed()["total"] == 1

    (tmp_path / "exploitation" / f"{written.exploitation_record_id}.json").unlink()

    assert index.feed()["total"] == 0


def test_a_backend_without_stamps_still_works_by_listing(lake):

    publish(lake, "https://a.example/first-story-in-the-lake")

    counting = CountingLake(lake, stamps=False)
    index = ReaderIndex(counting)

    assert index.feed()["total"] == 1

    publish(lake, "https://a.example/second-story-in-the-lake")

    assert index.feed()["total"] == 2
    # Listed every time, but each processed record is read once.
    assert counting.reads["list:exploitation"] == 2
    assert counting.reads[DataLayer.PROCESSED] == 2


def test_an_unplaceable_record_is_skipped_not_fatal(lake):

    publish(lake)

    lake.backend.write(DataLayer.EXPLOITATION, "odd", {"record_id": "odd", "publishable": True})

    assert ReaderIndex(lake).feed()["total"] == 1


# ----------------------------------------------------------------------
# The article view
# ----------------------------------------------------------------------


def test_an_article_carries_every_claim_its_sources_and_why_each_was_trusted(lake):

    publish(lake, checks=[
        checked(),
        checked(
            claim="The wetland was drained in the 1960s.",
            verdict=Verdict.UNVERIFIED,
            evidence=[],
            cited_evidence_indices=[],
            rejected_sources=[],
            search_unavailable=True,
        ),
    ])

    index = ReaderIndex(lake)

    item = index.feed()["items"][0]
    view = index.article(item["id"])

    assert view["author"] == "A. Reporter"
    # No YAMLs given to this index, so "bbc" names nothing: the domain is
    # shown, never a bare internal id.
    assert view["source"] == {"id": "bbc", "name": "bbc.com", "domain": "bbc.com"}
    assert view["verdict"]["counts"] == {"TRUE": 1}
    assert view["verdict"]["searchUnavailable"] == 1
    assert view["uncheckedClaims"] == ["The valley is beautiful."]

    first, second = view["claims"]

    assert first["outcome"] == "judged"
    assert second["outcome"] == "search_unavailable"

    cited, unrated = first["sources"]

    assert cited["cited"] is True
    assert cited["stance"] == "supports"
    assert cited["reliabilityKnown"] is True
    assert cited["scores"]["reliability"] == 0.85
    assert cited["scores"]["pertinence"] == 0.71
    assert cited["foundBy"] == ["anchor", "proposition"]
    # Capped like the live events: a source is a pointer, not a reprint.
    assert len(cited["snippet"]) == 240
    assert len(cited["quote"]) == 400

    assert unrated["cited"] is False
    assert unrated["reliabilityKnown"] is False

    # The ranked-but-uncited source is a source, not also a rejection.
    assert [item["url"] for item in first["notUsed"]] == ["https://elsewhere.example/etymology"]

    assert SCRAPED_BODY not in repr(view)


def test_an_unknown_or_unpublished_article_is_none(lake):

    publish(lake, "https://a.example/judged-false-story-here", verdict=Verdict.FALSE)

    index = ReaderIndex(lake)

    assert index.article(reader_id("https://a.example/judged-false-story-here")) is None
    assert index.article("0" * 16) is None
