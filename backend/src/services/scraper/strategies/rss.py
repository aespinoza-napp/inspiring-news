"""
RSS discovery strategy.
"""
from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit

import feedparser

from src.models.core.source import NewsSource
from src.services.scraper.fetcher import Fetcher
from src.config.topic_url_patterns import (
    INDEX_SEGMENTS,
    LIVE_COVERAGE,
    OFF_MISSION_SECTIONS,
    TOPIC_SECTION_PATTERNS_ES,
    TOPIC_URL_PATTERNS,
)
from src.config.topics import TOPIC_KEYWORDS_ES, TOPICS
from .base import DiscoveryStrategy


# A date in the path is the most language-independent sign of an article:
# /2026/09/23/, /2026-09-23/, /20260923/.
DATED_PATH = re.compile(r"/(20\d{2})[/-]?(0[1-9]|1[0-2])[/-]?(0[1-9]|[12]\d|3[01])(/|$|-)")

# ABC stamps its slugs with the moment of publication, to the second:
# ".../calcula-hipoteca-20260525124640-nt.html".
SLUG_TIMESTAMP = re.compile(r"(?<!\d)(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])([01]\d|2[0-3])[0-5]\d[0-5]\d(?!\d)")

# A slug this many words long is a headline, not a section name.
MIN_SLUG_WORDS = 4

# The language TOPICS' keywords are written in. Matching them against a
# feed in another language filters at random - see _filters_by_topic.
KEYWORD_LANGUAGE = "en"

# A feed summary is often the whole lead in HTML; the candidate list and
# the AI selection need a sentence or two, not the article.
SUMMARY_CHARS = 400

# Section path segment -> the topics it files an article under, English
# and Spanish section names together. Read only to decide whether a link
# belongs to a topic that was *not* asked for (filed_under); whether a
# link looks like an article at all is still _is_article's call.
_SECTIONS = {
    topic: tuple(TOPIC_URL_PATTERNS.get(topic, ())) + tuple(TOPIC_SECTION_PATTERNS_ES.get(topic, ()))
    for topic in TOPICS
}


def off_mission(url: str) -> bool:
    """Filed under a section this publication never covers (OFF_MISSION_SECTIONS), or live coverage."""

    path = urlsplit(url.lower()).path

    return any(marker in path for marker in OFF_MISSION_SECTIONS + LIVE_COVERAGE)


def date_from_url(url: str) -> datetime | None:
    """
    The publication date a link carries in its own path - /2026/10/06/,
    /2026-10-06/, /20261006/, or ABC's slug stamp - as midnight UTC; None
    when it carries none. Only for judging an undated link's age: day
    precision is no publication time (the freshness report keeps to
    feed times).
    """

    path = urlsplit(url).path

    found = DATED_PATH.search(path) or SLUG_TIMESTAMP.search(path)

    if not found:
        return None

    try:
        return datetime(int(found.group(1)), int(found.group(2)), int(found.group(3)), tzinfo=timezone.utc)
    except ValueError:
        return None


def _index_page(path: str) -> bool:
    """A category, tag, author or special-collection index (INDEX_SEGMENTS)."""

    return any(segment in path for segment in INDEX_SEGMENTS)


def filed_under(url: str) -> set[str]:
    """
    The topics a link's own path files it under - "/ciencia/" is
    research, "/medio-ambiente/" climate - or an empty set when its path
    names no section (a dated slug, /digest/...). The path only, so a
    host name cannot match.
    """

    path = urlsplit(url.lower()).path

    return {
        topic
        for topic, sections in _SECTIONS.items()
        if any(section in path for section in sections)
    }


@dataclass(frozen=True)
class DiscoveredLink:
    """One feed item: its link, and what the feed says about it."""

    url: str

    # When the feed says it was published; None when it does not say.
    published: datetime | None = None

    title: str | None = None

    # The feed's own summary, as plain text and cut to SUMMARY_CHARS.
    summary: str | None = None


class RSSDiscoveryStrategy(DiscoveryStrategy):
    """Discover article URLs from an RSS feed."""

    ARTICLE_PATTERNS = (
        "/article/",
        "/articles/",
        "/story/",
        "/stories/",
        "/world/",
        "/technology/",
        "/tech/",
        "/science/",
        "/health/",
        "/environment/",
        "/climate/",
        "/culture/",
        "/travel/",
        "/food/",
        "/sport/",
        "/sports/",
        "/features/",
        "/feature/",
        "/latest/",
    )

    _ALL_TOPIC_URL_PATTERNS = {
        pattern
        for patterns in TOPIC_URL_PATTERNS.values()
        for pattern in patterns
    }

    def __init__(self, fetcher: Fetcher | None = None):

        # The feed is fetched here, not by feedparser: feedparser's own
        # HTTP has no timeout (a dead feed held discovery for 20s+ in the
        # live check) and bypasses the URL guard.
        self.fetcher = fetcher or Fetcher()

    def discover(
        self,
        source: NewsSource,
        topics: list[str] = None,
    ) -> list[str]:

        return [url for url, _ in self.discover_entries(source, topics)]

    def discover_entries(
        self,
        source: NewsSource,
        topics: list[str] = None,
    ) -> list[tuple[str, datetime | None]]:
        """
        Each article URL with the time the feed says it was published -
        the most precise publication time there is: an article page
        often states only its date, a feed item its minute and timezone.
        It is what the freshness report measures reception against
        (src/services/freshness.py).
        """

        return [(item.url, item.published) for item in self.discover_items(source, topics)]

    def discover_items(
        self,
        source: NewsSource,
        topics: list[str] = None,
    ) -> list[DiscoveredLink]:
        """
        Every article link the feed carries for the topics asked for,
        with its time, title and summary - what a person or the AI
        selection reads to choose among candidates before any page is
        fetched (src/services/ingestion_service.py).

        Dropped here, before anything is fetched: links that do not look
        like articles, links in an off-mission section (sport, celebrity,
        horoscopes - OFF_MISSION_SECTIONS), and, when topics were asked
        for, links whose own path files them under a topic that was not
        (an El País "/ciencia/" link when only Environment was picked)
        unless the item mentions one that was.
        A link whose path names no section is left to the keyword
        filter: on an English feed, always; on a Spanish one, only when
        the run was narrowed to some topics (TOPIC_KEYWORDS_ES) - asked
        for everything, a Spanish feed keeps every article and topic is
        the admission filter's call, as it always was.
        """

        if not source.rss_url:
            return []

        feed = feedparser.parse(self.fetcher.get(str(source.rss_url)).html)

        items: dict[str, DiscoveredLink] = {}

        normalized_topics = {
            topic.lower().strip()
            for topic in (topics or [])
        }

        keywords = self._keywords_for(normalized_topics)
        url_patterns = self._url_patterns_for(normalized_topics)
        by_topic = self._filters_by_topic(source)

        spanish = (
            _spanish_keywords_for(normalized_topics)
            if _language(source) == "es" and _narrowed(normalized_topics)
            else set()
        )

        for entry in feed.entries:

            link = getattr(entry, "link", None)

            if not link:
                continue

            if not self._is_article(link) or off_mission(link):
                continue

            filed = filed_under(link)
            in_section = bool(filed & normalized_topics)

            mentions_en = by_topic and self._matches_keywords(entry, keywords)
            mentions_es = bool(spanish) and _mentions(entry, spanish)

            # Filed under a topic not asked for, and saying nothing about
            # one that was. A section is a coarse label: elDiario files
            # wind-power records under /economia/, and those stay.
            if normalized_topics and filed and not in_section and not (mentions_en or mentions_es):
                continue

            matches_url = any(
                pattern in link.lower()
                for pattern in url_patterns
            )

            if by_topic and not matches_url and not mentions_en:
                continue

            if spanish and not in_section and not mentions_es:
                continue

            if link not in items:
                items[link] = DiscoveredLink(
                    url=link,
                    published=_entry_time(entry),
                    title=_plain(getattr(entry, "title", None)),
                    summary=_plain(getattr(entry, "summary", None), SUMMARY_CHARS),
                )

        return list(items.values())

    @staticmethod
    def _filters_by_topic(source: NewsSource) -> bool:
        """
        Whether the keyword pre-filter can say anything about this
        source. Every TOPICS keyword is English, so against a Spanish feed
        it matched almost nothing and dropped articles at random (El País:
        149 entries, 5 kept). For those sources discovery keeps every
        article-shaped link and leaves topic to the admission filter,
        which rejects before any LLM call - a scrape and an enrichment
        each, not a fact-check.
        """

        return _language(source) == KEYWORD_LANGUAGE

    def _keywords_for(self, topics: set[str]) -> set[str]:
        """
        Expands topic ids (e.g. "space") into their configured keyword
        vocabulary (e.g. "nasa", "mars", ...). Matching the bare topic id
        against article text is unreliable - the id itself rarely appears
        verbatim in a title or summary.
        """

        return {
            keyword.lower()
            for topic in topics
            if topic in TOPICS
            for keyword in TOPICS[topic].keywords
        }

    def _url_patterns_for(self, topics: set[str]) -> set[str]:

        return {
            pattern
            for topic in topics
            for pattern in TOPIC_URL_PATTERNS.get(topic, ())
        }

    def _matches_keywords(
        self,
        entry,
        keywords: set[str],
    ) -> bool:
        """
        Returns True if the RSS entry's title/summary/categories mention
        one of the requested topics' keywords.
        """

        if not keywords:
            return False

        title = getattr(entry, "title", "")
        summary = getattr(entry, "summary", "")

        categories = " ".join(
            tag.get("term", "")
            for tag in getattr(entry, "tags", [])
        )

        searchable = (
            f"{title} {summary} {categories}"
        ).lower()

        return any(
            keyword in searchable
            for keyword in keywords
        )

    def _is_article(
        self,
        url: str,
    ) -> bool:
        """
        A link "looks like" an article if its path matches one of the
        generic article patterns, or one of the topic-specific URL
        patterns from any configured topic (a "/space/" or "/medicine/"
        segment is essentially always an article, not a homepage/about
        page - regardless of which topic the caller currently asked for).

        Video pages are rejected outright, even if their path also
        contains an article-shaped segment. Some sources (e.g. CNN)
        nest video URLs under the same category segments as real
        articles (.../videos/world/...), so an unqualified substring
        match on "/world/" would let a video page through - and video
        pages extract as player/caption UI chrome, not article prose,
        which produced nonsense "claims" downstream (verified live:
        ClaimExtractor scored a caption fragment like "3:05 �
        Source:" at 0.90 confidence).
        """

        url = url.lower()

        if "/video/" in url or "/videos/" in url:
            return False

        path = urlsplit(url).path

        if _index_page(path):
            return False

        # The English section names above missed nearly every Spanish
        # article (El Mundo 26 of 26, La Vanguardia 130 of 132) and every
        # NASA one. A date in the path or a headline-length slug says
        # "article" in any language; a homepage or a section index has
        # neither.
        slug = re.sub(r"\.html?$", "", path.rstrip("/").rsplit("/", 1)[-1])

        return (
            any(pattern in url for pattern in self.ARTICLE_PATTERNS)
            or any(pattern in url for pattern in self._ALL_TOPIC_URL_PATTERNS)
            or bool(DATED_PATH.search(path))
            or len([word for word in re.split(r"[-_]", slug) if word]) >= MIN_SLUG_WORDS
        )


def _entry_time(entry) -> datetime | None:
    """
    feedparser normalises pubDate (or, failing it, the updated date) to
    a UTC struct_time; None when the item has neither, or an unreadable
    one. Never "now": a missing time must stay missing.
    """

    for name in ("published_parsed", "updated_parsed"):

        value = getattr(entry, name, None)

        if value:
            try:
                return datetime(*value[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue

    return None


_TAGS = re.compile(r"<[^>]+>")
_SPACES = re.compile(r"\s+")


def _plain(value, limit: int | None = None) -> str | None:
    """A feed field as one line of plain text: tags and entities gone, cut to `limit`."""

    if not value:
        return None

    text = _SPACES.sub(" ", html.unescape(_TAGS.sub(" ", str(value)))).strip()

    if limit and len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + "…"

    return text or None


# Path segments that name an article page whatever its section.
ARTICLE_SEGMENTS = ("/article/", "/articles/", "/story/", "/stories/")


def article_shaped(url: str) -> bool:
    """
    A link that looks like an article by its own shape - a date in the
    path, a headline-length slug, an /article/ segment - not by the
    section it sits in. What a section page's links are judged by: every
    link on /culture/ contains "/culture/", so _is_article's section
    patterns say nothing there, and on 2026-10-05 BBC's section pages
    gave /culture/music and /sustainability/strategy as Environment
    candidates.
    """

    lowered = url.lower()

    if "/video/" in lowered or "/videos/" in lowered:
        return False

    path = urlsplit(lowered).path

    if _index_page(path):
        return False

    slug = re.sub(r"\.html?$", "", path.rstrip("/").rsplit("/", 1)[-1])

    return (
        any(segment in path for segment in ARTICLE_SEGMENTS)
        or bool(DATED_PATH.search(path))
        or len([word for word in re.split(r"[-_]", slug) if word]) >= MIN_SLUG_WORDS
    )


def _language(source: NewsSource) -> str:

    return (source.language or KEYWORD_LANGUAGE).lower()[:2]


def _narrowed(topics: set[str]) -> bool:
    """Asked for some topics, not all of them: a topic-scoped run (/discover, POST /ingest with groups)."""

    return bool(topics) and not set(TOPICS) <= topics


def _spanish_keywords_for(topics: set[str]) -> set[str]:

    return {keyword for topic in topics for keyword in TOPIC_KEYWORDS_ES.get(topic, ())}


_NOT_WORD = re.compile(r"[^\w]+")


def _folded(text: str) -> str:
    """Lower case, no accents, words separated by single spaces and padded: " el delta recupera aves "."""

    decomposed = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))

    return " " + _NOT_WORD.sub(" ", plain).strip() + " "


def _mentions(entry, keywords: set[str]) -> bool:
    """
    Whether a feed item's title or categories contain a word starting
    with one of `keywords` - "energ" finds "energía" and "energético"; a
    keyword ending in a space ("arte ") is a whole word, so "parte" is
    not "arte". Not the summary: see TOPIC_KEYWORDS_ES.
    """

    categories = " ".join(tag.get("term", "") for tag in getattr(entry, "tags", []))
    text = _folded(f"{getattr(entry, 'title', '')} {categories}")

    return any(f" {keyword}" in text for keyword in keywords)
