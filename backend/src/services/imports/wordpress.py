"""
A WordPress export (WXR, Tools > Export) read into articles the pipeline can
take as they are: no page is fetched, so the text analysed is exactly the
text in the file, and a later run on the same file, verified this time, is
judged on the same words (services/imports/wordpress_import.py).

Built for inspiringnews.ai's export of 2026-11-03: 1,122 items, of which 462
posts - 187 published (2025-2026, Spanish), 272 private (2024-2025, 171 of
them in English) and 3 drafts - and 660 attachments, which are skipped.

What is kept from a post: its id, link, title, text, dates, status, its
categories and tags, its author's display name, the outside pages its text
links to, the list of sources it ends with, and its photos. **Not** the
authors' e-mail addresses, which the export carries in its header and which
nothing here needs.

Two things a post's text no longer carries (2026-11-20, asked for by the
author):

- **Its list of sources.** 101 of the 187 published posts end in one
  ("Fuentes:" and the outlets, "Fuente original: <link>", or a bare list of
  links). Read as text, it put the outlets among the story's own names, and
  the heading itself: GLiNER read "Fuentes" as a person's surname in 5
  posts. It is cut from the text before anything reads it and kept beside
  it, as `source_list`: the section a reader sees, item by item.
- **Nothing of its photos was kept**, though every published post has one
  (`_thumbnail_id`, an attachment of the same export) and 59 more in their
  text. `images` holds each with its alt text, caption and the sizes
  WordPress made of it; `scripts/wordpress_images.py` downloads them.

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
# The caption is kept with its image instead (Post.images).
_SKIPPED = frozenset({"script", "style", "noscript", "figcaption", "iframe", "svg", "button", "form"})

# The heading of the list of sources a post ends with, as the 2026-11-03
# export writes it: "Fuentes:" (75 posts), "Fuente original: <link>" (11),
# "Fuente: <link>" (9), "Fuentes" (6). Alone on its line, or a colon and the
# source after it. "Fuentes de la catedral resaltan..." is a sentence of the
# story, not a heading: no colon.
_SOURCES_HEADING = re.compile(
    r"^(?:fuentes?(?: original(?:es)?| consultadas)?|referencias|bibliograf[ií]a|sources?)\s*(?::\s*(?P<rest>.*))?$",
    re.IGNORECASE,
)

# A line of a list of sources is an outlet, a study or a link, never a
# paragraph: the longest in the export is 120 characters. A heading followed
# by a line longer than this is not at the end of the post, so it is not cut.
_SOURCE_LINE = 200

_BULLET = re.compile(r"^\s*(?:[-–—•*·]|\d+[.)])\s+")
_URL = re.compile(r"https?://\S+")


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
    # them by link (126 of the 462 posts do). Those of `source_list` too.
    sources: list[str] = field(default_factory=list)

    # The list of sources the post ends with, cut from `text`: each item as
    # the reader sees it ("PETA Asia", "Euronews ES") and its link when the
    # item has one, in order. [] when the post lists none.
    source_list: list[dict] = field(default_factory=list)

    # Its photos: the featured one first (`featured: true`), then those in
    # its text, in order. Each: url, alt, caption, width, height,
    # attachment_id and the sizes WordPress made ({name: {url, width,
    # height}}, "thumbnail" 150 px and "medium_large" 768 px for nearly all).
    images: list[dict] = field(default_factory=list)

    # The featured photo's url, else the first in the text's.
    image_url: str | None = None

    # sha256 of `text`: what says two runs read the same words. Imports
    # before 2026-11-20 hashed the text with its list of sources.
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
        # (href, the text inside the link), for telling which item of a list
        # of sources a link belongs to.
        self.anchors: list[tuple[str, str]] = []
        # Each <img>: its src, alt, class, and the caption of its figure.
        self.images: list[dict] = []
        self._skipping = 0
        self._anchor: list[str] | None = None
        self._caption: list[str] | None = None
        self._figure_start = 0

    def handle_starttag(self, tag, attrs):

        attributes = dict(attrs)

        if tag in _SKIPPED:
            self._skipping += 1
        elif tag in _BLOCKS:
            self.parts.append("\n")

        if tag == "a":
            href = attributes.get("href")
            if href:
                self.links.append(href)
                self.anchors.append((href, ""))
                self._anchor = []

        elif tag == "img":
            self.images.append({
                "src": (attributes.get("src") or "").strip(),
                "alt": (attributes.get("alt") or "").strip() or None,
                "class": attributes.get("class") or "",
                "width": attributes.get("width"),
                "height": attributes.get("height"),
                "caption": None,
            })

        elif tag == "figure":
            self._figure_start = len(self.images)

        elif tag == "figcaption":
            self._caption = []

    def handle_endtag(self, tag):

        if tag in _SKIPPED:
            self._skipping = max(0, self._skipping - 1)
        elif tag in _BLOCKS:
            self.parts.append("\n")

        if tag == "a" and self._anchor is not None:
            href, _ = self.anchors[-1]
            self.anchors[-1] = (href, " ".join("".join(self._anchor).split()))
            self._anchor = None

        elif tag == "figcaption" and self._caption is not None:
            caption = " ".join("".join(self._caption).split())
            # The caption of the figure's own image, not of one before it.
            if caption and len(self.images) > self._figure_start:
                self.images[-1]["caption"] = caption
            self._caption = None

    def handle_data(self, data):

        if self._caption is not None:
            self._caption.append(data)

        # Whitespace in HTML is one space, a line break inside a <p> too.
        if not self._skipping:
            self.parts.append(re.sub(r"\s+", " ", data))
            if self._anchor is not None:
                self._anchor.append(data)


@dataclass
class Markup:
    """A post's content as a reader sees it: its lines, links and images."""

    lines: list[str]
    links: list[str]
    anchors: list[tuple[str, str]]
    images: list[dict]


def read_markup(markup: str | None) -> Markup:

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

    return Markup(lines=lines, links=parser.links, anchors=parser.anchors, images=parser.images)


def html_to_text(markup: str | None) -> tuple[str, list[str]]:
    """The text a reader sees, a paragraph a line, and every link in it."""

    read = read_markup(markup)

    return "\n\n".join(read.lines), read.links


def _fold(text: str) -> str:
    return " ".join(text.casefold().split()).rstrip(".;,: ")


def _source_item(line: str, outside: dict[str, str]) -> dict:
    """One item of a list of sources: as the reader sees it, and its link if it has one."""

    text = _BULLET.sub("", line).strip().rstrip(".;,").strip()
    found = _URL.search(text)

    if found and found.group(0).rstrip(".,;)") == text.rstrip(".,;)"):
        url = text.rstrip(".,;)")
        return {"text": _host(url) or url, "url": url}

    url = outside.get(_fold(text)) or (found.group(0).rstrip(".,;)") if found else None)

    if url is None:
        # "Telemundo / Associated Press" linked as "Associated Press": the
        # line holds the link's text.
        url = next((href for name, href in outside.items() if name and name in _fold(text)), None)

    return {"text": text, "url": url}


def split_sources(lines: list[str], anchors: list[tuple[str, str]], own_host: str) -> tuple[list[str], list[dict]]:
    """
    (the post's lines without its list of sources, the list's items). Three
    shapes, all seen in the 2026-11-03 export:

    - a heading alone ("Fuentes:", "Fuentes") and every line after it short:
      the list runs to the end of the post;
    - a heading and its source on one line ("Fuente original: <link>"),
      wherever it is: such a line is never a sentence of the story;
    - no heading, the post ending in lines that are each a link to another
      site, whole ("Earthly Mission", "IFL Science").

    The first line is never cut: a post that is only a list keeps its text.
    """

    outside = {
        _fold(text): href.strip()
        for href, text in anchors
        if text and href.strip().startswith(("http://", "https://")) and not _own(href, own_host)
    }

    body = list(lines)
    tail: list[str] = []

    for i in range(len(body) - 1, 0, -1):
        heading = _SOURCES_HEADING.match(body[i])
        if heading and not (heading.group("rest") or "").strip():
            if all(len(line) <= _SOURCE_LINE for line in body[i + 1:]):
                tail = body[i + 1:]
                body = body[:i]
            break

    inline: list[str] = []
    kept: list[str] = []

    for index, line in enumerate(body):
        heading = _SOURCES_HEADING.match(line)
        rest = (heading.group("rest") or "").strip() if heading else ""
        if index and heading and rest and len(rest) <= _SOURCE_LINE:
            inline.append(rest)
        else:
            kept.append(line)

    body = kept

    if not tail:
        while len(body) > 1 and len(body[-1]) <= _SOURCE_LINE and _fold(body[-1]) in outside:
            tail.insert(0, body.pop())

    return body, [_source_item(line, outside) for line in inline + tail]


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


def _own(url: str, own_host: str) -> bool:

    host = _host(url.strip())

    return not host or host == own_host or host.endswith("." + own_host)


def _outside_links(links: list[str], own_host: str) -> list[str]:

    kept = []

    for link in links:

        link = link.strip()

        if not link.startswith(("http://", "https://")):
            continue

        if _own(link, own_host):
            continue

        if link not in kept:
            kept.append(link)

    return kept


def clean_url(url: str | None) -> str | None:
    """
    An image's address with one slash where the export has two: every
    attachment of 2026-11-03 is "https://inspiringnews.ai//wp-content/...".
    The site answers both; one spelling keeps one photo one file.
    """

    url = (url or "").strip()

    if not url.startswith(("http://", "https://")):
        return None

    parts = urlsplit(url)

    return parts._replace(path=re.sub(r"/{2,}", "/", parts.path)).geturl()


def _int(value) -> int | None:

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# WordPress keeps an attachment's dimensions and the sizes it made of it as
# a PHP-serialised array (_wp_attachment_metadata). Only these fields are
# read, by pattern: unserialising PHP is not worth a parser.
_META_WIDTH = re.compile(r's:5:"width";i:(\d+);')
_META_HEIGHT = re.compile(r's:6:"height";i:(\d+);')
_META_SIZE = re.compile(
    r's:\d+:"(?P<name>[\w-]+)";a:\d+:\{s:4:"file";s:\d+:"(?P<file>[^"]+)";'
    r's:5:"width";i:(?P<width>\d+);s:6:"height";i:(?P<height>\d+);'
)


def _postmeta(item) -> dict[str, str]:

    return {
        (meta.findtext("wp:meta_key", namespaces=NS) or ""): meta.findtext("wp:meta_value", namespaces=NS) or ""
        for meta in item.findall("wp:postmeta", NS)
    }


def _attachment_image(item) -> dict | None:
    """An attachment of the export as an image: its url, alt, caption, dimensions and sizes."""

    url = clean_url(item.findtext("wp:attachment_url", namespaces=NS) or item.findtext("guid"))

    if url is None:
        return None

    meta = _postmeta(item)
    serialised = meta.get("_wp_attachment_metadata", "")
    width, height = _META_WIDTH.search(serialised), _META_HEIGHT.search(serialised)
    folder = url.rsplit("/", 1)[0]

    sizes = {
        size["name"]: {"url": f"{folder}/{size['file']}", "width": int(size["width"]), "height": int(size["height"])}
        for size in _META_SIZE.finditer(serialised)
        # A size's file sits beside the original; a path in it is not one.
        if "/" not in size["file"]
    }

    return {
        "url": url,
        "alt": meta.get("_wp_attachment_image_alt", "").strip() or None,
        "caption": html_to_text(item.findtext("excerpt:encoded", namespaces=NS))[0] or None,
        "width": int(width.group(1)) if width else None,
        "height": int(height.group(1)) if height else None,
        "attachment_id": _int(item.findtext("wp:post_id", namespaces=NS)),
        "sizes": sizes,
    }


_WP_IMAGE = re.compile(r"\bwp-image-(\d+)\b")


def post_images(featured: dict | None, inline: list[dict], attachments: dict[int, dict]) -> list[dict]:
    """
    The post's photos, the featured one first, each once. An image in the
    text that names its attachment (class "wp-image-5814") takes the
    attachment's sizes, and its alt when the tag has none; its caption is
    the figure's.
    """

    images: list[dict] = []
    seen: set = set()

    def add(image: dict, is_featured: bool) -> None:
        keys = {image["url"], image.get("attachment_id")} - {None}
        if keys & seen:
            return
        seen.update(keys)
        images.append({**image, "featured": is_featured})

    if featured:
        add(featured, True)

    for tag in inline:

        url = clean_url(tag["src"])

        if url is None:
            continue

        match = _WP_IMAGE.search(tag["class"])
        attachment = attachments.get(int(match.group(1))) if match else None
        known = attachment or {}

        # The attachment's dimensions are the original's: they describe the
        # tag only when it shows the original, not one of its sizes.
        original = url == known.get("url")

        add({
            "url": url,
            "alt": tag["alt"] or known.get("alt"),
            "caption": tag["caption"] or known.get("caption"),
            "width": _int(tag["width"]) or (known.get("width") if original else None),
            "height": _int(tag["height"]) or (known.get("height") if original else None),
            "attachment_id": known.get("attachment_id"),
            "sizes": known.get("sizes") or {},
        }, False)

    return images


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

    # The photos are attachments, items of their own (660 in the export of
    # 2026-11-03); a post names its featured one by id.
    attachments: dict[int, dict] = {}

    for item in items:
        if item.findtext("wp:post_type", namespaces=NS) == "attachment":
            image = _attachment_image(item)
            if image and image["attachment_id"] is not None:
                attachments[image["attachment_id"]] = image

    for item in items:

        if item.findtext("wp:post_type", namespaces=NS) != "post":
            continue

        status = (item.findtext("wp:status", namespaces=NS) or "").strip()

        if status not in statuses:
            continue

        markup = read_markup(item.findtext("content:encoded", namespaces=NS))
        lines, source_list = split_sources(markup.lines, markup.anchors, own_host)
        text, links = "\n\n".join(lines), markup.links

        if not text:
            continue

        featured_id = _int(_postmeta(item).get("_thumbnail_id"))
        images = post_images(attachments.get(featured_id) if featured_id else None, markup.images, attachments)

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
            source_list=source_list,
            images=images,
            image_url=images[0]["url"] if images else None,
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
