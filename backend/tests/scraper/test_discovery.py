import feedparser

from src.models.core.source import NewsSource, SourceType
from src.services.scraper.strategies.rss import RSSDiscoveryStrategy


def make_source(**kwargs) -> NewsSource:

    defaults = dict(
        id="test",
        name="Test Source",
        base_url="https://example.com",
        rss_url="https://example.com/rss.xml",
        source_type=SourceType.NEWS,
    )

    defaults.update(kwargs)

    return NewsSource(**defaults)


def entry(link: str, title: str, summary: str = "") -> feedparser.FeedParserDict:

    return feedparser.FeedParserDict(link=link, title=title, summary=summary)


class FakeFeed:

    def __init__(self, entries):
        self.entries = entries


def test_discover_matches_by_topic_keyword(monkeypatch):

    entries = [
        entry("https://example.com/space/nasa-launch", "NASA launches new telescope"),
        entry("https://example.com/sport/football-final", "Football final result"),
    ]

    monkeypatch.setattr(feedparser, "parse", lambda url: FakeFeed(entries))

    strategy = RSSDiscoveryStrategy()

    urls = strategy.discover(make_source(), topics=["space"])

    assert urls == ["https://example.com/space/nasa-launch"]


def test_discover_matches_by_url_pattern_even_without_keyword(monkeypatch):

    entries = [
        entry("https://example.com/space/some-headline", "Some headline"),
    ]

    monkeypatch.setattr(feedparser, "parse", lambda url: FakeFeed(entries))

    strategy = RSSDiscoveryStrategy()

    urls = strategy.discover(make_source(), topics=["space"])

    assert urls == ["https://example.com/space/some-headline"]


def test_discover_ignores_unrelated_topics(monkeypatch):

    entries = [
        entry("https://example.com/sport/football-final", "Football final result"),
    ]

    monkeypatch.setattr(feedparser, "parse", lambda url: FakeFeed(entries))

    strategy = RSSDiscoveryStrategy()

    urls = strategy.discover(make_source(), topics=["space"])

    assert urls == []


def test_discover_ignores_non_article_links(monkeypatch):

    entries = [
        entry("https://example.com/about-us", "space mission announced"),
    ]

    monkeypatch.setattr(feedparser, "parse", lambda url: FakeFeed(entries))

    strategy = RSSDiscoveryStrategy()

    urls = strategy.discover(make_source(), topics=["space"])

    assert urls == []


def test_discover_deduplicates_links(monkeypatch):

    entries = [
        entry("https://example.com/space/nasa-launch", "NASA launches new telescope"),
        entry("https://example.com/space/nasa-launch", "NASA launches new telescope"),
    ]

    monkeypatch.setattr(feedparser, "parse", lambda url: FakeFeed(entries))

    strategy = RSSDiscoveryStrategy()

    urls = strategy.discover(make_source(), topics=["space"])

    assert urls == ["https://example.com/space/nasa-launch"]


def test_discover_returns_empty_without_rss_url():

    strategy = RSSDiscoveryStrategy()

    urls = strategy.discover(make_source(rss_url=None), topics=["space"])

    assert urls == []
