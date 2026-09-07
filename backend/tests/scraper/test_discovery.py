import feedparser

from src.services.scraper.strategies.rss import RSSDiscoveryStrategy

from tests.builders.source_builder import build_source


def make_source(**kwargs):

    kwargs.setdefault("rss_url", "https://example.com/rss.xml")

    return build_source(**kwargs)


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


def test_discover_with_no_topics_returns_empty_instead_of_crashing(monkeypatch):
    """
    `topics` defaults to None in the method signature, so it must be a
    genuinely supported input, not just an unused default - calling this
    directly (bypassing Scraper.discover(), which happens to always
    substitute a real topic list) used to raise
    `TypeError: 'NoneType' object is not iterable`.
    """

    entries = [
        entry("https://example.com/space/nasa-launch", "NASA launches new telescope"),
    ]

    monkeypatch.setattr(feedparser, "parse", lambda url: FakeFeed(entries))

    strategy = RSSDiscoveryStrategy()

    assert strategy.discover(make_source(), topics=None) == []


def test_discover_matches_bbc_style_flat_article_urls(monkeypatch):
    """
    BBC's current RSS feed links to /news/articles/<opaque-id> - no topic
    segment in the path at all. Verified live against the real feed: every
    single BBC article failed the generic "looks like an article" gate
    before this pattern was added, so BBC discovery always returned 0 URLs
    regardless of which topics were requested.
    """

    entries = [
        entry(
            "https://www.bbc.co.uk/news/articles/cy4zejgz3z9o?at_medium=RSS",
            "NASA confirms new Mars mission timeline",
        ),
    ]

    monkeypatch.setattr(feedparser, "parse", lambda url: FakeFeed(entries))

    strategy = RSSDiscoveryStrategy()

    urls = strategy.discover(make_source(), topics=["space"])

    assert urls == ["https://www.bbc.co.uk/news/articles/cy4zejgz3z9o?at_medium=RSS"]


def test_discover_excludes_video_pages_even_with_matching_url_segment(monkeypatch):
    """
    Some sources (e.g. CNN) nest video URLs under the same category
    segments as real articles (.../videos/world/...). An unqualified
    substring match on "/world/" let those through, and video pages
    extract as player/caption UI chrome rather than article prose -
    verified live: ClaimExtractor scored a caption fragment at 0.90
    confidence as if it were a real claim.
    """

    entries = [
        entry(
            "https://www.cnn.com/videos/space/2023/04/02/nasa-launch-vpx.cnn",
            "NASA launches new telescope",
        ),
    ]

    monkeypatch.setattr(feedparser, "parse", lambda url: FakeFeed(entries))

    strategy = RSSDiscoveryStrategy()

    # Same topic/keyword match as test_discover_matches_by_topic_keyword
    # above - proving it's specifically the "/videos/" segment, not a
    # topic/keyword mismatch, that excludes this one.
    assert strategy.discover(make_source(), topics=["space"]) == []
