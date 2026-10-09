from datetime import datetime, timedelta, timezone

from src.models.core.source import JsonFeed
from src.services.scraper.discovery import DiscoveryService
from src.services.scraper.request_stats import RequestStats
from src.services.scraper.strategies.listings import (
    JsonFeedDiscoveryStrategy,
    NewsSitemapDiscoveryStrategy,
    json_feed_entries,
    news_sitemap_entries,
)

from tests.builders.source_builder import build_source


# Shaped as CNN's was on 2026-10-09: a live page, a video, shopping, a
# health story and a 2025 review that never left the sitemap.
CNN_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
  <url>
    <loc>https://www.cnn.com/2026/10/09/health/overcoming-odds-series-amy-narcolepsy-wellness</loc>
    <news:news>
      <news:publication><news:name>CNN</news:name><news:language>en</news:language></news:publication>
      <news:publication_date>2026-10-09T11:00:00Z</news:publication_date>
      <news:title>For decades, no one could explain her exhaustion and hallucinations</news:title>
      <news:keywords>health, sleep, narcolepsy</news:keywords>
    </news:news>
  </url>
  <url>
    <loc>https://www.cnn.com/2026/10/09/world/live-news/nobel-peace-prize-2026-winner-intl</loc>
    <news:news>
      <news:publication><news:name>CNN</news:name><news:language>en</news:language></news:publication>
      <news:publication_date>2026-10-09T07:13:00Z</news:publication_date>
      <news:title>Nobel Peace Prize goes to South African human rights pioneer Navi Pillay</news:title>
    </news:news>
  </url>
  <url>
    <loc>https://www.cnn.com/2026/10/09/us/video/fema-hurricane-isaias-ready-to-respond-craig-fugate</loc>
    <news:news>
      <news:publication><news:name>CNN</news:name><news:language>en</news:language></news:publication>
      <news:publication_date>2026-10-09T11:17:00Z</news:publication_date>
      <news:title>As Hurricane Isaias closes in on the Gulf Coast, is FEMA ready?</news:title>
    </news:news>
  </url>
  <url>
    <loc>https://www.cnn.com/cnn-underscored/deals/best-amazon-prime-day-deals-2026-10-09</loc>
    <news:news>
      <news:publication><news:name>CNN</news:name><news:language>en</news:language></news:publication>
      <news:publication_date>2026-10-09T10:38:00Z</news:publication_date>
      <news:title>October Prime Day may be over, but 50 of the best Amazon deals are still live</news:title>
    </news:news>
  </url>
  <url>
    <loc>https://www.cnn.com/cnn-underscored/reviews/best-cutting-boards-health-kitchen</loc>
    <news:news>
      <news:publication><news:name>CNN</news:name><news:language>en</news:language></news:publication>
      <news:publication_date>2025-12-11T19:40:00Z</news:publication_date>
      <news:title>We tested a baker's dozen of the best cutting boards</news:title>
    </news:news>
  </url>
</urlset>"""


class Canned:

    def __init__(self, body):
        self.body = body
        self.asked = []

    def get(self, url):
        self.asked.append(url)
        return type("Page", (), {"html": self.body, "url": url, "status": 200})()


def test_a_news_sitemap_gives_each_articles_title_time_and_keywords():

    first = news_sitemap_entries(CNN_SITEMAP)[0]

    assert first.link == "https://www.cnn.com/2026/10/09/health/overcoming-odds-series-amy-narcolepsy-wellness"
    assert first.title.startswith("For decades")
    assert datetime(*first.published_parsed[:6], tzinfo=timezone.utc) == datetime(2026, 10, 9, 11, tzinfo=timezone.utc)
    assert [tag["term"] for tag in first.tags] == ["health", "sleep", "narcolepsy"]


def test_a_news_sitemaps_items_pass_the_feeds_filters():
    """Live pages, video and shopping go, as from a feed; an article of the topic stays."""

    fetcher = Canned(CNN_SITEMAP)
    cnn = build_source(id="cnn", news_sitemap_url="https://www.cnn.com/sitemap/news.xml")

    items = NewsSitemapDiscoveryStrategy(fetcher=fetcher).discover_items(cnn, topics=["medicine"])

    assert [item.url for item in items] == [
        "https://www.cnn.com/2026/10/09/health/overcoming-odds-series-amy-narcolepsy-wellness",
    ]
    assert items[0].title.startswith("For decades") and items[0].published is not None
    assert fetcher.asked == ["https://www.cnn.com/sitemap/news.xml"]


def test_a_source_without_a_news_sitemap_or_json_listing_is_not_read_for_one():

    plain = build_source()

    assert not NewsSitemapDiscoveryStrategy(fetcher=Canned("")).applies(plain)
    assert not JsonFeedDiscoveryStrategy(fetcher=Canned("")).applies(plain)
    assert NewsSitemapDiscoveryStrategy(fetcher=Canned("")).discover_items(plain, topics=["medicine"]) == []


WHO_API = """{"value": [
  {"Title": "New global roadmap launched to tackle hypertension in pregnancy",
   "ItemDefaultUrl": "/08-10-2026-new-global-roadmap-launched-to-tackle-hypertension-in-pregnancy",
   "PublicationDateAndTime": "2026-10-08T08:12:34Z"},
  {"Title": "WHO issues first global guidelines on child and adolescent obesity",
   "ItemDefaultUrl": "/07-10-2026-who-issues-first-global-guidelines-on-child-and-adolescent-obesity",
   "PublicationDateAndTime": "2026-10-07T10:00:00Z"},
  {"Title": "No link", "ItemDefaultUrl": null}
]}"""

WHO_FEED = JsonFeed(
    url="https://www.who.int/api/news/newsitems?$top=30",
    items="value",
    link="ItemDefaultUrl",
    link_prefix="https://www.who.int/news/item",
    title="Title",
    published="PublicationDateAndTime",
)


def test_a_json_listing_gives_links_titles_and_times():
    """WHO's news API on 2026-10-09, while its RSS feed's newest item was from February."""

    first, second = json_feed_entries(WHO_API, WHO_FEED)

    assert first.link == "https://www.who.int/news/item/08-10-2026-new-global-roadmap-launched-to-tackle-hypertension-in-pregnancy"
    assert first.title == "New global roadmap launched to tackle hypertension in pregnancy"
    assert datetime(*first.published_parsed[:6], tzinfo=timezone.utc) == datetime(2026, 10, 8, 8, 12, 34, tzinfo=timezone.utc)
    assert second.title.startswith("WHO issues")


def test_a_dead_feed_falls_through_to_the_json_listing():

    class DeadFeed:
        def get(self, url):
            return type("Page", (), {"html": "<rss><channel></channel></rss>"})()

    from src.services.scraper.strategies.rss import RSSDiscoveryStrategy

    who = build_source(
        id="who", base_url="https://www.who.int", rss_url="https://www.who.int/rss-feeds/news-english.xml",
        groups=["health"], json_feed=WHO_FEED.model_dump(mode="json"),
    )

    result = DiscoveryService(
        [RSSDiscoveryStrategy(fetcher=DeadFeed()), JsonFeedDiscoveryStrategy(fetcher=Canned(WHO_API))],
        stats=RequestStats(),
        max_age=timedelta(days=30),
    ).run(who, topics=["medicine", "mental_health", "nutrition", "fitness", "public_health"])

    assert result.method == "JsonFeedDiscoveryStrategy"
    # Neither title has a Health keyword: WHO publishes nothing else, so none is needed.
    assert len(result.urls) == 2
    assert result.details[result.urls[0]]["title"].startswith("New global roadmap")


def test_a_source_with_other_groups_than_those_asked_for_still_needs_a_keyword():

    from src.services.scraper.strategies.rss import covers_only

    health = {"medicine", "mental_health", "nutrition", "fitness", "public_health"}

    assert covers_only(build_source(groups=["health"]), health)
    assert not covers_only(build_source(groups=["health", "science"]), health)
    assert not covers_only(build_source(groups=[]), health)
    # Asked for everything: the keywords run as they always did.
    from src.config.topics import TOPICS
    assert not covers_only(build_source(groups=["health"]), set(TOPICS))
