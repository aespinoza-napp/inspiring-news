"""
A WordPress export (WXR, Tools > Export) read into articles the pipeline can
take as they are: no page is fetched, so the text analysed is exactly the
text in the file, and a later run on the same file, verified this time, is
judged on the same words (services/imports/wordpress_import.py).

Built for inspiringnews.ai's export of 2026-11-03: 1,122 items, of which 462
posts - 187 published (2025-2026, Spanish), 272 private (2024-2025, 171 of
them in English) and 3 drafts - and 660 attachments, which are skipped.

What is kept from a post: its id, link, title, text, dates, status, its
categories and tags, its author's display name, and the outside pages its
text links to. **Not** the authors' e-mail addresses, which the export
carries in its header and which nothing here needs.

Standard library only. The file is someone's export, so a DOCTYPE is refused
before parsing: WXR has none, and one is how entity expansion gets in.
"""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

NS = {
    "wp": "http://wordpress.org/export/1.2/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "excerpt": "http://wordpress.org/export/1.2/excerpt/",
    "dc": "http://purl.org/dc/elements/1.1/",
}

STATUSES = ("publish", "private", "draft", "pending", "future")

# Tags whose end starts a new paragraph of text.
_BLOCKS = frozenset({
    "p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "section", "article", "header", "footer", "tr", "table", "hr",
})

# Tags whose content is not the article's text: code, and an image's caption
# or credit ("Foto: EFE"), which would otherwise read as a sentence of it.
_SKIPPED = frozenset({"script", "style", "noscript", "figcaption", "iframe", "svg", "button", "form"})


class NotAnExport(ValueError):
    """The file is not a WordPress export, or one this cannot read safely."""


@dataclass
class Post:

    wp_id: int
    url: str
    title: str
    text: str
    status: str
    published_at: str | None
    modified_at: str | None
    language: str | None
    author: str | None
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    # Outside pages the text links to: the article's sources, when it names
    # them by link (126 of the 462 posts do).
    sources: list[str] = field(default_factory=list)

    # sha256 of `text`: what says two runs read the same words.
    content_hash: str = ""

    # The earlier post carrying the same text, or the same title: the export
    # has 14 titles twice. Recorded, never dropped - a duplicate is one of
    # the things the comparison is about.
    duplicate_of: int | None = None

    def row(self) -> dict:
        return asdict(self)


@dataclass
class Export:

    site: str
    base_url: str
    language: str | None
    items: int
    posts: list[Post]


class _Text(HTMLParser):

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.links: list[str] = []
        self._skipping = 0

    def handle_starttag(self, tag, attrs):

        if tag in _SKIPPED:
            self._skipping += 1
        elif tag in _BLOCKS:
            self.parts.append("\n")

        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag):

        if tag in _SKIPPED:
            self._skipping = max(0, self._skipping - 1)
        elif tag in _BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data):

        # Whitespace in HTML is one space, a line break inside a <p> too.
        if not self._skipping:
            self.parts.append(re.sub(r"\s+", " ", data))


def html_to_text(markup: str | None) -> tuple[str, list[str]]:
    """The text a reader sees, a paragraph a line, and every link in it."""

    # Gutenberg's block comments (<!-- wp:paragraph -->) are comments, and
    # the parser drops them; Elementor's shortcodes are not, so they go here.
    markup = re.sub(r"\[/?[a-z_][\w-]*[^\]]*\]", " ", markup or "")

    # The classic editor stores no <p>: WordPress adds them when it serves
    # the post (wpautop), a blank line a paragraph and a line break a <br>.
    if not re.search(r"<(p|br|div|h[1-6]|li)\b", markup, re.IGNORECASE):
        markup = re.sub(r"\n\s*\n", "</p><p>", markup.strip()).replace("\n", "<br>")

    parser = _Text()
    parser.feed(markup)
    parser.close()

    lines = []

    for line in "".join(parser.parts).replace("\xa0", " ").split("\n"):
        line = re.sub(r"[ \t\r\f\v]+", " ", line).strip()
        if line:
            lines.append(line)

    return "\n\n".join(lines), parser.links


def _date(value: str | None) -> str | None:
    """WordPress's GMT date as ISO 8601 in UTC; None for a draft's zero date."""

    if not value or value.startswith("0000"):
        return None

    try:
        moment = datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None

    return moment.replace(tzinfo=timezone.utc).isoformat()


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def _outside_links(links: list[str], own_host: str) -> list[str]:

    kept = []

    for link in links:

        link = link.strip()

        if not link.startswith(("http://", "https://")):
            continue

        host = _host(link)

        if not host or host == own_host or host.endswith("." + own_host):
            continue

        if link not in kept:
            kept.append(link)

    return kept


def _title_key(title: str) -> str:
    return re.sub(r"\W+", " ", title.lower()).strip()


def read(path: str | Path, statuses: tuple[str, ...] = ("publish",)) -> Export:
    """
    The posts of `path` whose status is in `statuses`, oldest first. The
    default is what the site shows today: its published posts.
    """

    data = Path(path).read_bytes()

    return parse(data, statuses)


def parse(data: bytes, statuses: tuple[str, ...] = ("publish",)) -> Export:

    head = data[:4096].lower()

    if b"<!doctype" in head or b"<!entity" in data.lower():
        raise NotAnExport("The file declares a DOCTYPE or entities; a WordPress export has none.")

    unknown = set(statuses) - set(STATUSES)

    if unknown:
        raise NotAnExport(f"Unknown post status: {', '.join(sorted(unknown))}. Use: {', '.join(STATUSES)}.")

    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError as exc:
        raise NotAnExport(f"Not well-formed XML: {exc}") from None

    channel = root.find("channel")

    if root.tag != "rss" or channel is None or channel.find("wp:wxr_version", NS) is None:
        raise NotAnExport("Not a WordPress export: no <channel> with a wp:wxr_version.")

    base_url = (channel.findtext("wp:base_site_url", namespaces=NS) or channel.findtext("link") or "").strip()
    own_host = _host(base_url)

    # Login -> display name. The e-mail addresses beside them stay unread.
    authors = {
        (author.findtext("wp:author_login", namespaces=NS) or "").strip():
            (author.findtext("wp:author_display_name", namespaces=NS) or "").strip() or None
        for author in channel.findall("wp:author", NS)
    }

    items = channel.findall("item")
    posts: list[Post] = []

    for item in items:

        if item.findtext("wp:post_type", namespaces=NS) != "post":
            continue

        status = (item.findtext("wp:status", namespaces=NS) or "").strip()

        if status not in statuses:
            continue

        text, links = html_to_text(item.findtext("content:encoded", namespaces=NS))

        if not text:
            continue

        wp_id = int(item.findtext("wp:post_id", namespaces=NS) or 0)
        url = (item.findtext("link") or "").strip() or f"{base_url.rstrip('/')}/?p={wp_id}"
        login = (item.findtext("dc:creator", namespaces=NS) or "").strip()

        posts.append(Post(
            wp_id=wp_id,
            url=url,
            title=html.unescape((item.findtext("title") or "").strip()),
            text=text,
            status=status,
            published_at=_date(item.findtext("wp:post_date_gmt", namespaces=NS)),
            modified_at=_date(item.findtext("wp:post_modified_gmt", namespaces=NS)),
            # The site's declared language; the enrichment detects each
            # post's own from its text, which is what decides its lexicon.
            language=None,
            author=authors.get(login),
            categories=[c.text.strip() for c in item.findall("category") if c.get("domain") == "category" and c.text],
            tags=[c.text.strip() for c in item.findall("category") if c.get("domain") == "post_tag" and c.text],
            sources=_outside_links(links, own_host),
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        ))

    posts.sort(key=lambda post: (post.published_at or "9999", post.wp_id))

    seen_text: dict[str, int] = {}
    seen_title: dict[str, int] = {}

    for post in posts:

        key = _title_key(post.title)
        post.duplicate_of = seen_text.get(post.content_hash) or (seen_title.get(key) if key else None)

        seen_text.setdefault(post.content_hash, post.wp_id)
        if key:
            seen_title.setdefault(key, post.wp_id)

    return Export(
        site=(channel.findtext("title") or "").strip(),
        base_url=base_url,
        language=(channel.findtext("language") or "").strip() or None,
        items=len(items),
        posts=posts,
    )
