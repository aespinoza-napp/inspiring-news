"""
The second parser in the cascade: reads the same HTML trafilatura just
failed on, with a different idea of where an article lives.

Trafilatura's heuristics are good and general; where they miss, it is
usually because the page says what it is in a way they do not read - the
full text sitting in a JSON-LD `articleBody` behind a thin teaser, or a
layout whose article is split across divs no heuristic would call the
main content. So this tries, cheapest and most reliable first:

1. what the page declares about itself (JSON-LD, then meta tags),
2. CSS selectors the source's YAML names (`metadata.selectors`),
3. the container holding the most paragraph text.

It never fetches: the cascade hands it the page trafilatura already
downloaded (see `strategies/html.py`).
"""

from __future__ import annotations

import json
from typing import Iterable

from bs4 import BeautifulSoup, Tag

from src.models.core.source import NewsSource
from src.models.scraper.extraction import ExtractionResult
from src.services.scraper.fetcher import FetchedPage

from .html import HtmlStrategy

# Elements that are never the article, removed before measuring text.
NOISE = [
    "script", "style", "noscript", "template", "svg", "form",
    "nav", "header", "footer", "aside", "iframe", "button",
]

# Where an article's paragraphs usually live, checked before falling
# back to "whichever element holds the most paragraph text".
CONTAINERS = [
    "article",
    "[itemprop='articleBody']",
    "main",
    "[role='main']",
]

# A paragraph shorter than this is a caption, a byline or a share button.
MIN_PARAGRAPH = 40

ARTICLE_TYPES = {"Article", "NewsArticle", "ReportageNewsArticle", "BlogPosting"}


class BeautifulSoupStrategy(HtmlStrategy):

    def parse(self, source: NewsSource, page: FetchedPage) -> ExtractionResult | None:

        soup = BeautifulSoup(page.html, "lxml")

        declared = _json_ld_article(soup)
        selectors = (source.metadata or {}).get("selectors") or {}

        # Read before the noise is stripped: bylines and dates often sit
        # in the very <header> that is about to be removed.
        metadata = _metadata(soup, declared, selectors)

        for tag in soup(NOISE):
            tag.decompose()

        body = (
            _select_paragraphs(soup, selectors.get("body"))
            or _text(declared.get("articleBody"))
            or _densest_paragraphs(soup)
        )

        if not body:
            return None

        return ExtractionResult(source_id=source.id, body=body, **metadata)

    @staticmethod
    def metadata(source: NewsSource, page: FetchedPage) -> dict:
        """
        Title, author, date, summary and image from a page, without
        looking for the article at all. For filling the gaps another
        parser left: trafilatura often finds the text and misses a byline
        sitting in a meta tag or the JSON-LD.
        """

        soup = BeautifulSoup(page.html, "lxml")

        return _metadata(
            soup,
            _json_ld_article(soup),
            (source.metadata or {}).get("selectors") or {},
        )


def _metadata(soup: BeautifulSoup, declared: dict, selectors: dict) -> dict:

    title = (
        _select_text(soup, selectors.get("title"))
        or _text(declared.get("headline"))
        or _meta(soup, "og:title", "twitter:title")
        or _first_text(soup, "h1")
        or _first_text(soup, "title")
    )

    author = (
        _select_text(soup, selectors.get("author"))
        or _author(declared.get("author"))
        or _meta(soup, "author", "article:author")
        or _first_text(soup, "[rel='author']")
    )

    published = (
        _select_attr(soup, selectors.get("date"), "datetime")
        or _text(declared.get("datePublished"))
        or _meta(soup, "article:published_time", "date", "pubdate")
        or _first_attr(soup, "time[datetime]", "datetime")
    )

    return {
        "title": title,
        "author": author,
        "published_at": _date_only(published),
        "summary": _meta(soup, "og:description", "description"),
        "lead_image": _meta(soup, "og:image"),
    }


def _text(value) -> str | None:

    if isinstance(value, list):
        value = value[0] if value else None

    if not isinstance(value, str):
        return None

    value = " ".join(value.split())

    return value or None


def _date_only(value: str | None) -> str | None:
    """YYYY-MM-DD from an ISO timestamp; None rather than a guess."""

    if not value or len(value) < 10 or value[4] != "-" or value[7] != "-":
        return None

    return value[:10]


def _meta(soup: BeautifulSoup, *names: str) -> str | None:

    for name in names:

        tag = soup.find("meta", attrs={"property": name}) or soup.find(
            "meta", attrs={"name": name}
        )

        if tag and _text(tag.get("content")):
            return _text(tag.get("content"))

    return None


def _first_text(soup: BeautifulSoup, selector: str) -> str | None:

    tag = soup.select_one(selector)

    return _text(tag.get_text(" ")) if tag else None


def _first_attr(soup: BeautifulSoup, selector: str, attribute: str) -> str | None:

    tag = soup.select_one(selector)

    return _text(tag.get(attribute)) if tag else None


def _select_text(soup: BeautifulSoup, selector: str | None) -> str | None:

    return _first_text(soup, selector) if selector else None


def _select_attr(soup: BeautifulSoup, selector: str | None, attribute: str) -> str | None:

    if not selector:
        return None

    tag = soup.select_one(selector)

    if not tag:
        return None

    return _text(tag.get(attribute)) or _text(tag.get_text(" "))


def _select_paragraphs(soup: BeautifulSoup, selector: str | None) -> str | None:

    if not selector:
        return None

    container = soup.select_one(selector)

    return _paragraphs(container) if container else None


def _paragraphs(container: Tag) -> str | None:

    texts = [
        text
        for paragraph in container.find_all("p")
        if (text := _text(paragraph.get_text(" "))) and len(text) >= MIN_PARAGRAPH
    ]

    return "\n\n".join(texts) or None


def _densest_paragraphs(soup: BeautifulSoup) -> str | None:
    """
    The usual containers first; failing those, whichever element's own
    paragraphs add up to the most text. "Own" matters: <body> contains
    every paragraph on the page, so it would always win by summing its
    children's - it is the parent of each paragraph that is measured.
    """

    for selector in CONTAINERS:

        container = soup.select_one(selector)

        if container:
            body = _paragraphs(container)
            if body:
                return body

    totals: dict[int, tuple[Tag, int]] = {}

    for paragraph in soup.find_all("p"):

        text = _text(paragraph.get_text(" "))
        parent = paragraph.parent

        if not text or len(text) < MIN_PARAGRAPH or parent is None:
            continue

        tag, total = totals.get(id(parent), (parent, 0))
        totals[id(parent)] = (tag, total + len(text))

    if not totals:
        return None

    best, _ = max(totals.values(), key=lambda entry: entry[1])

    return _paragraphs(best)


def _json_ld_article(soup: BeautifulSoup) -> dict:
    """The first schema.org article object the page declares, or {}."""

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):

        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        for item in _flatten(data):
            kinds = item.get("@type")
            kinds = kinds if isinstance(kinds, list) else [kinds]

            if ARTICLE_TYPES.intersection(k for k in kinds if isinstance(k, str)):
                return item

    return {}


def _flatten(data) -> Iterable[dict]:
    """JSON-LD nests articles in lists and in `@graph`; walk all of it."""

    if isinstance(data, list):
        for item in data:
            yield from _flatten(item)

    elif isinstance(data, dict):
        yield data
        yield from _flatten(data.get("@graph") or [])


def _author(value) -> str | None:

    if isinstance(value, list):
        names = [name for item in value if (name := _author(item))]
        return ", ".join(names) or None

    if isinstance(value, dict):
        return _text(value.get("name"))

    return _text(value)
