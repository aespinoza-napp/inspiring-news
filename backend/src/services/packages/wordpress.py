"""
A draft as a WordPress post: `post.json`, the body of a REST API request
(POST /wp-json/wp/v2/posts), and `post.xml`, one item of a WordPress
eXtended RSS file (WXR 1.2) for Tools -> Import -> WordPress.

Both are drafts: `status` is "draft" in each, so nothing is public on the
site until a person publishes it there. The body is the draft's Markdown
as HTML, each [n] a superscript link to its source in a numbered list at
the end, then the fact-checks and the AI disclosure, as the reader's own
page shows them (frontend reader/stories/[id]).

**Sending** is the one network call in packages, made only when a person
asks (POST .../packages/{id}/wordpress) and only when WORDPRESS_URL,
WORDPRESS_USER and WORDPRESS_APP_PASSWORD are all set: an application
password over HTTPS basic auth, the site's own documented way
(developer.wordpress.org/rest-api/using-the-rest-api/authentication/).
Tags go in post.xml by name; the REST API wants tag ids the site
assigns, so post.json leaves them out and the manifest says so.
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from xml.sax.saxutils import escape

import requests

from src.config.settings import settings
from src.models.writer.draft import ArticleDraft
from src.models.writer.package import WordPressDelivery
from src.services.corrector import grounding
from src.services.packages.content import PackageContent

VERDICT_LABELS = {
    "es": {"TRUE": "Verdadero", "PARTIALLY_TRUE": "Parcialmente verdadero", "FALSE": "Falso",
           "MISLEADING": "Engañoso", "UNVERIFIED": "Sin verificar", "NOT_CHECKED": "No comprobado"},
    "en": {"TRUE": "True", "PARTIALLY_TRUE": "Partly true", "FALSE": "False",
           "MISLEADING": "Misleading", "UNVERIFIED": "Unverified", "NOT_CHECKED": "Not checked"},
    "ca": {"TRUE": "Cert", "PARTIALLY_TRUE": "Parcialment cert", "FALSE": "Fals",
           "MISLEADING": "Enganyós", "UNVERIFIED": "Sense verificar", "NOT_CHECKED": "No comprovat"},
}

HEADINGS = {
    "es": ("Fuentes", "Verificación del artículo original"),
    "en": ("Sources", "Fact-checks of the original article"),
    "ca": ("Fonts", "Verificació de l'article original"),
}


class WordPressNotConfigured(RuntimeError):
    pass


class WordPressRefused(RuntimeError):
    pass


def configured() -> bool:

    return bool(settings.WORDPRESS_URL and settings.WORDPRESS_USER and settings.WORDPRESS_APP_PASSWORD)


# ----------------------------------------------------------------------
# The body
# ----------------------------------------------------------------------


def _inline(text: str, source_count: int) -> str:

    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)

    def cite(match: re.Match) -> str:
        number = int(match.group(1))
        if 1 <= number <= source_count:
            return f'<sup><a href="#source-{number}">[{number}]</a></sup>'
        return match.group(0)

    return grounding.CITATION.sub(cite, text)


def body_html(draft: ArticleDraft, content: PackageContent) -> str:
    """The Markdown body ArticleBody renders (headings, lists, paragraphs, **bold**, [n]) as HTML."""

    count = len(draft.sources)
    parts: list[str] = []

    for block in re.split(r"\n\s*\n", draft.content.body.replace("\r\n", "\n")):

        block = block.strip()
        if not block:
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", block)
        lines = [line.strip() for line in block.split("\n") if line.strip()]

        if heading and len(lines) == 1:
            level = min(max(len(heading.group(1)), 2), 4)
            parts.append(f"<h{level}>{_inline(heading.group(2), count)}</h{level}>")
        elif all(re.match(r"^[-*] ", line) for line in lines):
            items = "".join(f"<li>{_inline(line[2:], count)}</li>" for line in lines)
            parts.append(f"<ul>{items}</ul>")
        else:
            parts.append(f"<p>{_inline(' '.join(lines), count)}</p>")

    sources_title, checks_title = HEADINGS.get(draft.language, HEADINGS["en"])

    if draft.sources:
        items = "".join(
            f'<li id="source-{number}"><a href="{html.escape(source.url)}" rel="noopener">'
            f"{html.escape(source.title or source.domain)}</a> ({html.escape(source.domain)})</li>"
            for number, source in enumerate(draft.sources, start=1)
        )
        parts.append(f"<h2>{sources_title}</h2><ol>{items}</ol>")

    if draft.fact_checks:
        labels = VERDICT_LABELS.get(draft.language, VERDICT_LABELS["en"])
        items = "".join(
            f"<li><strong>{labels.get(check.verdict.upper(), check.verdict)}</strong>: "
            f"{html.escape(check.claim)}</li>"
            for check in draft.fact_checks
        )
        parts.append(f"<h2>{checks_title}</h2><ul>{items}</ul>")

    if content.link:
        parts.append(f'<p><a href="{html.escape(content.link)}">{html.escape(content.link)}</a></p>')

    parts.append(f"<p><em>{html.escape(content.disclosure)}</em></p>")

    return "\n".join(parts)


# ----------------------------------------------------------------------
# The files
# ----------------------------------------------------------------------


def post_json(draft: ArticleDraft, content: PackageContent) -> dict:

    return {
        "title": draft.content.title,
        "content": body_html(draft, content),
        "excerpt": draft.metadata.seo_description or draft.content.subtitle,
        "status": "draft",
        "slug": draft.metadata.slug or None,
        "comment_status": "closed",
        "meta": {},
    }


def post_xml(draft: ArticleDraft, content: PackageContent, created: datetime | None = None) -> str:
    """A one-item WXR 1.2 file, status draft, tags by name."""

    created = created or datetime.now(timezone.utc)
    stamp = created.strftime("%Y-%m-%d %H:%M:%S")

    def cdata(text: str) -> str:
        return "<![CDATA[" + text.replace("]]>", "]]]]><![CDATA[>") + "]]>"

    tags = "".join(
        f'\n      <category domain="post_tag" nicename="{escape(_slug(tag))}">{cdata(tag)}</category>'
        for tag in draft.metadata.tags
    )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:excerpt="http://wordpress.org/export/1.2/excerpt/"
  xmlns:content="http://purl.org/rss/1.0/modules/content/"
  xmlns:dc="http://purl.org/dc/elements/1.1/"
  xmlns:wp="http://wordpress.org/export/1.2/">
  <channel>
    <title>{escape(content.brand)}</title>
    <language>{escape(draft.language)}</language>
    <wp:wxr_version>1.2</wp:wxr_version>
    <item>
      <title>{cdata(draft.content.title)}</title>
      <dc:creator>{cdata(content.brand)}</dc:creator>
      <content:encoded>{cdata(body_html(draft, content))}</content:encoded>
      <excerpt:encoded>{cdata(draft.metadata.seo_description or draft.content.subtitle)}</excerpt:encoded>
      <wp:post_date>{stamp}</wp:post_date>
      <wp:post_date_gmt>{stamp}</wp:post_date_gmt>
      <wp:post_name>{cdata(draft.metadata.slug or _slug(draft.content.title))}</wp:post_name>
      <wp:status>draft</wp:status>
      <wp:post_type>post</wp:post_type>
      <wp:comment_status>closed</wp:comment_status>{tags}
    </item>
  </channel>
</rss>
"""


def _slug(text: str) -> str:

    return re.sub(r"[^\w]+", "-", text.casefold()).strip("-")[:80]


# ----------------------------------------------------------------------
# Sending
# ----------------------------------------------------------------------


def send_draft(post: dict, session: requests.Session | None = None) -> WordPressDelivery:
    """
    The post created on the configured site as a draft. Raises
    WordPressNotConfigured without the three settings, WordPressRefused
    when the site answers with anything but a created post. `status` is
    forced to draft here as well as in the file: whatever post.json says,
    this never publishes.
    """

    if not configured():
        raise WordPressNotConfigured(
            "Set WORDPRESS_URL, WORDPRESS_USER and WORDPRESS_APP_PASSWORD in backend/.env to send packages to a site."
        )

    base = settings.WORDPRESS_URL.rstrip("/")

    if not base.startswith("https://") and not base.startswith("http://localhost"):
        raise WordPressRefused("WORDPRESS_URL must be https://: an application password is sent with every request.")

    body = {key: value for key, value in {**post, "status": "draft"}.items() if value is not None}

    http = session or requests.Session()

    try:
        response = http.post(
            f"{base}/wp-json/wp/v2/posts",
            data=json.dumps(body),
            headers={"Content-Type": "application/json"},
            auth=(settings.WORDPRESS_USER, settings.WORDPRESS_APP_PASSWORD.get_secret_value()),
            timeout=settings.WORDPRESS_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise WordPressRefused(f"The site could not be reached: {type(exc).__name__}") from exc

    if response.status_code != 201:
        try:
            detail = response.json().get("message") or ""
        except ValueError:
            detail = ""
        raise WordPressRefused(f"The site answered {response.status_code}{': ' + detail if detail else ''}")

    created = response.json()

    return WordPressDelivery(
        post_id=int(created.get("id")),
        status=str(created.get("status") or "draft"),
        link=f"{base}/wp-admin/post.php?post={created.get('id')}&action=edit",
        sent_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
