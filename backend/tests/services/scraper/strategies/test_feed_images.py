"""
The picture a feed gives each item (rss.entry_image, 2026-11-24): a link
only, carried to the candidate so /discover can show it beside the title.
Feeds are parsed by feedparser here, as discovery parses them.
"""

import feedparser

from src.services.scraper.strategies.listings import news_sitemap_entries
from src.services.scraper.strategies.rss import RSSDiscoveryStrategy, entry_image

from tests.builders.source_builder import build_source


def feed(item: str) -> feedparser.FeedParserDict:

    return feedparser.parse(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel><title>T</title>'
        f"<item><title>A story</title><link>https://news.example/2026/11/24/a-story-about-mangroves</link>{item}</item>"
        "</channel></rss>"
    ).entries[0]


LINK = "https://news.example/2026/11/24/a-story-about-mangroves"


def test_media_content_marked_as_an_image_is_the_picture():

    entry = feed(
        '<media:content url="https://cdn.example/video.mp4" medium="video"/>'
        '<media:content url="https://cdn.example/mangroves.jpg" medium="image"/>'
    )

    assert entry_image(entry, LINK) == "https://cdn.example/mangroves.jpg"


def test_a_thumbnail_or_an_image_enclosure_does_when_there_is_no_media_content():

    assert entry_image(feed('<media:thumbnail url="https://cdn.example/thumb.webp"/>'), LINK) == "https://cdn.example/thumb.webp"

    enclosure = feed(
        '<enclosure url="https://cdn.example/podcast.mp3" type="audio/mpeg" length="1"/>'
        '<enclosure url="https://cdn.example/photo.png" type="image/png" length="1"/>'
    )

    assert entry_image(enclosure, LINK) == "https://cdn.example/photo.png"


def test_else_the_first_real_image_of_the_summary_read_against_the_articles_link():

    entry = feed(
        "<description><![CDATA["
        '<img src="https://feeds.example/~r/pixel" width="1" height="1"/>'
        '<p>Mangroves cut storm waves.</p><img src="/images/mangroves.jpg?w=800&amp;h=600" alt=""/>'
        "]]></description>"
    )

    assert entry_image(entry, LINK) == "https://news.example/images/mangroves.jpg?w=800&h=600"


def test_no_picture_and_nothing_that_is_not_a_web_link():

    assert entry_image(feed("<description>Only words.</description>"), LINK) is None
    assert entry_image(feed('<description><![CDATA[<img src="data:image/png;base64,AAAA"/>]]></description>'), LINK) is None
    assert entry_image(feed('<media:thumbnail url="javascript:alert(1)"/>'), LINK) is None


def test_a_news_sitemaps_image_extension_is_its_items_picture():

    [entry] = news_sitemap_entries(
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:news="http://www.google.com/schemas/sitemap-news/0.9" '
        'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">'
        f"<url><loc>{LINK}</loc>"
        "<news:news><news:title>A story</news:title></news:news>"
        "<image:image><image:loc>https://cdn.example/sitemap.jpg</image:loc></image:image>"
        "</url></urlset>"
    )

    assert entry_image(entry, LINK) == "https://cdn.example/sitemap.jpg"


def test_the_discovered_item_carries_it(monkeypatch):

    from src.services.scraper.fetcher import FetchedPage, Fetcher

    # Filed under a section the topic asked for, as in test_discovery's summary test.
    link = "https://news.example/environment/2026/11/24/mangroves-cut-storm-waves"
    rss = (
        '<?xml version="1.0"?><rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel><title>T</title>'
        f"<item><title>Mangroves cut storm waves</title><link>{link}</link>"
        '<media:content url="https://cdn.example/mangroves.jpg" medium="image"/></item>'
        "</channel></rss>"
    )

    monkeypatch.setattr(Fetcher, "get", lambda self, url: FetchedPage(url=url, status=200, html=rss))

    [item] = RSSDiscoveryStrategy().discover_items(build_source(rss_url="https://news.example/rss.xml"), topics=["climate"])

    assert item.image == "https://cdn.example/mangroves.jpg"
