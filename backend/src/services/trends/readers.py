"""
Reading a trend signal's feed into trends (docs/decisions/trends.md).

Pure functions over the text a feed returned: the fetching, the counting
and the failures are TrendService's (services/trends/trend_service.py),
so every reader here is tested on the feeds saved on 2026-10-26
(tests/fixtures/trends/) and never reads the live web.

Google Trends' RSS is parsed with the standard library's ElementTree, not
feedparser: each item carries several `ht:news_item` elements, and
feedparser keeps only the last of a repeated namespaced element. The
expat underneath refuses the entity-expansion attacks a hostile XML could
try (2.4 and later; 2.6.4 here).
"""

from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ElementTree
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urlsplit

import feedparser

from src.models.core.trend_signal import TrendSignal
from src.services.trends.trends import Trend, TrendArticle, trend_id

# A snippet is a sentence or two for the person choosing, not the page.
SNIPPET_CHARS = 400

# Reddit's own hosts: a post linking here is a self-post, an image or a
# video on Reddit - a thread, not an article to analyse.
REDDIT_HOSTS = ("reddit.com", "redd.it")

# The "[link]" anchor of a Reddit post: where the post points.
_REDDIT_LINK = re.compile(r'<a href="([^"]+)">\s*\[link\]\s*</a>')

_TAGS = re.compile(r"<[^>]+>")
_SPACES = re.compile(r"\s+")


class FeedError(ValueError):
    """The signal answered with something that is not the feed it should be."""


def parse_traffic(value: str | None) -> int | None:
    """
    Google's approximate searches as a number: "500+" -> 500, "2,000+" ->
    2000, "10K+" -> 10000, "1M+" -> 1000000. None for nothing readable.
    """

    if not value:
        return None

    text = value.strip().upper().replace(",", "").replace(".", "").replace(" ", "").rstrip("+")

    multiplier = 1

    if text.endswith("K"):
        multiplier, text = 1_000, text[:-1]
    elif text.endswith("M"):
        multiplier, text = 1_000_000, text[:-1]

    return int(text) * multiplier if text.isdigit() else None


def plain(value, limit: int | None = None) -> str | None:
    """A feed field as one line of plain text: tags and entities gone, cut to `limit`."""

    if not value:
        return None

    text = _SPACES.sub(" ", html.unescape(_TAGS.sub(" ", str(value)))).strip()

    if limit and len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + "…"

    return text or None


def _local(tag: str) -> str:
    """An element's name without its namespace: "{https://...}approx_traffic" -> "approx_traffic"."""

    return tag.rsplit("}", 1)[-1]


def _child(element, name: str):

    return next((child for child in element if _local(child.tag) == name), None)


def _children(element, name: str) -> list:

    return [child for child in element if _local(child.tag) == name]


def _text(element, name: str) -> str | None:

    child = _child(element, name)

    return plain(child.text) if child is not None and child.text else None


def _rfc822(value: str | None) -> datetime | None:

    if not value:
        return None

    try:
        moment = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None

    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def explore_link(name: str, country: str | None) -> str:
    """Google Trends' own page for a search, where a person can see its curve."""

    geo = f"&geo={quote(country)}" if country else ""

    return f"https://trends.google.com/trends/explore?q={quote(name)}{geo}&date=now%201-d"


def read_google_trends(text: str, signal: TrendSignal) -> list[Trend]:
    """
    One trend per item: the search, its approximate searches, when it
    started rising (pubDate) and the news items Google attaches - each a
    title, a link and an outlet. Raises FeedError when the text is not an
    RSS feed.
    """

    try:
        root = ElementTree.fromstring(text.encode("utf-8") if isinstance(text, str) else text)
    except ElementTree.ParseError as exc:
        raise FeedError(f"not an XML feed: {exc}") from exc

    channel = _child(root, "channel")

    if _local(root.tag) != "rss" or channel is None:
        raise FeedError(f"not an RSS feed (root <{_local(root.tag)}>)")

    trends = []

    for position, item in enumerate(_children(channel, "item"), start=1):

        name = _text(item, "title")

        if not name:
            continue

        articles = []

        for news in _children(item, "news_item"):

            url = (_text(news, "news_item_url") or "").strip()

            if not url.lower().startswith(("http://", "https://")):
                continue

            articles.append(TrendArticle(
                url=url,
                title=_text(news, "news_item_title"),
                outlet=_text(news, "news_item_source"),
                snippet=plain(_text(news, "news_item_snippet"), SNIPPET_CHARS),
            ))

        trends.append(Trend(
            id=trend_id(signal.id, name),
            name=name,
            signal=signal.id,
            signal_name=signal.name,
            language=signal.language,
            position=position,
            traffic=parse_traffic(_text(item, "approx_traffic")),
            started_at=_rfc822(_text(item, "pubDate")),
            link=explore_link(name, signal.country),
            articles=articles,
            positive=signal.positive,
        ))

    return trends


def _entry_time(entry) -> datetime | None:

    for name in ("published_parsed", "updated_parsed"):

        value = getattr(entry, name, None) or entry.get(name)

        if value:
            try:
                return datetime(*value[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue

    return None


def _on_reddit(url: str) -> bool:

    host = (urlsplit(url).hostname or "").lower()

    return any(host == domain or host.endswith("." + domain) for domain in REDDIT_HOSTS)


def _entry_html(entry) -> str:

    content = entry.get("content") or []

    if content:
        return str(content[0].get("value") or "")

    return str(entry.get("summary") or "")


def read_ranked_feed(text: str, signal: TrendSignal) -> tuple[list[Trend], int]:
    """
    One trend per item, in the feed's order, with the page it points to as
    its article; and how many items were skipped. A Reddit post's article
    is the link it was submitted with, never the thread: a self-post, an
    image or a video on Reddit is skipped. Raises FeedError when the text
    is not a feed at all.
    """

    feed = feedparser.parse(text)

    # An HTML page ("Too many requests") parses without complaint as a feed
    # of nothing; only a recognised RSS or Atom version says it is a feed.
    if not feed.entries and not feed.get("version"):
        raise FeedError("not an RSS or Atom feed")

    trends = []
    skipped = 0

    for entry in feed.entries:

        name = plain(entry.get("title"))
        link = str(entry.get("link") or "")

        if not name or not link:
            skipped += 1
            continue

        thread = None

        if _on_reddit(link):

            found = _REDDIT_LINK.search(_entry_html(entry))
            submitted = html.unescape(found.group(1)) if found else ""

            if not submitted.lower().startswith(("http://", "https://")) or _on_reddit(submitted):
                skipped += 1
                continue

            thread, link = link, submitted

        started = _entry_time(entry)

        trends.append(Trend(
            id=trend_id(signal.id, name),
            name=name,
            signal=signal.id,
            signal_name=signal.name,
            language=signal.language,
            position=len(trends) + 1,
            started_at=started,
            link=thread or link,
            articles=[TrendArticle(
                url=link,
                title=name,
                # A post's text is the poster's, not the article's: only an
                # outlet's own feed gives a snippet worth reading.
                snippet=None if thread else plain(_entry_html(entry), SNIPPET_CHARS),
                # A post's time is when it was posted, not when the article
                # was; the article is dated by its own page or path.
                published=None if thread else started,
            )],
            positive=signal.positive,
        ))

    return trends, skipped


def read_oembed(text: str) -> dict | None:
    """
    TikTok's oEmbed answer as the video a story can show: its id (the
    player's), the caption and the author when given. None when the
    answer is not TikTok's or names no video.
    """

    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return None

    if not isinstance(data, dict) or str(data.get("provider_name") or "").lower() != "tiktok":
        return None

    video_id = str(data.get("embed_product_id") or "").strip()

    if not video_id.isdigit():
        return None

    return {
        "provider": "tiktok",
        "id": video_id,
        "title": plain(data.get("title"), SNIPPET_CHARS),
        "author": plain(data.get("author_name")),
    }
