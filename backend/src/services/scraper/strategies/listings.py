"""
Two more ways to a source's article list, for publishers whose RSS feed
has died, each read only when the source names one - and only when its
feed found nothing new (DiscoveryService tries the steps in order):

- **A news sitemap** (`news_sitemap_url`): Google News's format, which a
  news publisher keeps to be listed there - every article of the last two
  days with its `news:title` and `news:publication_date` (and sometimes
  `news:keywords`). CNN's feed stopped in 2024; on 2026-10-09 its news
  sitemap listed 268 articles of the day, titled and timed, where its
  section pages gave undated links titled from their slugs.
- **A JSON listing** (`json_feed`): the API a site's own news page reads
  from. WHO's RSS feed's newest item on 2026-10-09 was from February, and
  its news page lists nothing without JavaScript; its news API returned
  that week's releases (a roadmap on hypertension in pregnancy, the first
  guidelines on child obesity).

Not every publisher's sitemap is news: ABC's sitemap_news.xml still
listed 2021 blog posts on 2026-10-09, and WHO's sitemap index was last
written in 2018. The age limit drops those; a source is configured with
one only after it has been looked at.

Both hand their items to the RSS strategy's filters in the feed's own
shape (`link`, `title`, `summary`, `tags`, `published_parsed`): article
shape, off-mission sections, topics and keywords judge every link the
same way whichever step found it.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ElementTree
from datetime import datetime, timezone
from types import SimpleNamespace

from src.models.core.source import JsonFeed, NewsSource

from .rss import RSSDiscoveryStrategy


class NewsSitemapDiscoveryStrategy(RSSDiscoveryStrategy):

    def applies(self, source: NewsSource) -> bool:

        return source.news_sitemap_url is not None

    def _entries(self, source: NewsSource) -> list:

        if source.news_sitemap_url is None:
            return []

        return news_sitemap_entries(self.fetcher.get(str(source.news_sitemap_url)).html)


class JsonFeedDiscoveryStrategy(RSSDiscoveryStrategy):

    def applies(self, source: NewsSource) -> bool:

        return source.json_feed is not None

    def _entries(self, source: NewsSource) -> list:

        if source.json_feed is None:
            return []

        return json_feed_entries(self.fetcher.get(str(source.json_feed.url)).html, source.json_feed)


def news_sitemap_entries(xml: str) -> list[SimpleNamespace]:
    """
    Every <url> of a news sitemap that has a <loc>, as a feed entry. The
    namespaces are matched by local name: publishers declare them under
    different prefixes. Keywords become categories, as a feed's would.
    """

    # The standard parser: expat resolves no external entities, and since
    # 2.4 (Python 3.12 ships later) caps entity expansion. The URL is our
    # own YAML's; the body is the publisher's.
    root = ElementTree.fromstring(xml.strip().encode("utf-8"))

    entries = []

    for url in _children(root, "url"):

        link = _text(url, "loc")

        if not link:
            continue

        news = next(iter(_children(url, "news")), None)

        keywords = _text(news, "keywords") if news is not None else None

        entries.append(_entry(
            link=link,
            title=_text(news, "title") if news is not None else None,
            summary=None,
            published=_time(_text(news, "publication_date") if news is not None else None),
            keywords=[k.strip() for k in (keywords or "").split(",") if k.strip()],
        ))

    return entries


def json_feed_entries(body: str, spec: JsonFeed) -> list[SimpleNamespace]:
    """Each item of a JSON listing, as a feed entry; an item without a link is skipped."""

    items = json.loads(body)

    for key in filter(None, spec.items.split(".")):
        items = items[key]

    entries = []

    for item in items:

        link = item.get(spec.link)

        if not link:
            continue

        if spec.link_prefix and not str(link).startswith(("http://", "https://")):
            link = spec.link_prefix.rstrip("/") + "/" + str(link).lstrip("/")

        entries.append(_entry(
            link=link,
            title=item.get(spec.title),
            summary=item.get(spec.summary) if spec.summary else None,
            published=_time(item.get(spec.published)) if spec.published else None,
        ))

    return entries


def _entry(link: str, title, summary, published: datetime | None, keywords=()) -> SimpleNamespace:

    return SimpleNamespace(
        link=link,
        title=title or "",
        summary=summary or "",
        tags=[{"term": keyword} for keyword in keywords],
        published_parsed=published.utctimetuple() if published else None,
    )


def _local(tag: str) -> str:

    return tag.rsplit("}", 1)[-1]


def _children(element, name: str) -> list:

    return [child for child in element if _local(child.tag) == name]


def _text(element, name: str) -> str | None:

    for child in element:
        if _local(child.tag) == name:
            return (child.text or "").strip() or None

    return None


def _time(value) -> datetime | None:
    """An ISO 8601 / W3C time ("2026-10-09T10:38:00Z", "2026-10-09") in UTC; None when unreadable."""

    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)
