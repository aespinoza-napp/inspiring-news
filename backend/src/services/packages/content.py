"""
What every package says, taken from the draft once: the headline, the
points worth a card, who said each, the fact-checks, the link, the AI
disclosure and the hashtags - and the few words around them in the
draft's language.

Nothing here writes a word the draft does not have, except the fixed
labels in TEXT. A card's point is a sentence of the body as written,
citations taken out and named instead ("Fuente: europapress.es"): a
package is posted where nobody can check a [3].
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field

from src.config.lexicons import writing_lexicon_for
from src.models.writer.draft import ArticleDraft
from src.services.corrector import grounding
from src.services.publishing.story import PublishedStory
from src.services.publishing.web import public_path

# A point longer than this does not fit a card at a size anyone reads on
# a phone; the next sentence is taken instead. Never cut: a cut sentence
# says something else.
MAX_POINT_CHARS = 280
MIN_POINT_WORDS = 6

# Instagram counts at most 30 hashtags and 2,200 characters of caption;
# TikTok 2,200 for a video. Fewer tags read better than 30.
MAX_HASHTAGS = 8
CAPTION_LIMIT = 2200

# The fixed words of a package, per draft language. Catalan stays for
# drafts written in it before it stopped being offered (2026-11-10).
TEXT = {
    "es": {
        "brand": "Inspiring News",
        "brand_devastating": "Devastating News",
        "source": "Fuente",
        "sources": "Fuentes",
        "checked": "Verificado",
        "checked_line": "{judged} de {total} afirmaciones del artículo original, verificadas",
        "not_checked": "Sin verificar",
        "read_more": "Lee el artículo completo",
        "link_in_bio": "Enlace en la bio",
        "tap_link": "Toca el enlace",
        "swipe": "Desliza",
        "ai": "Escrito con IA ({models}).",
        "ai_edited": "Escrito con IA ({models}) y editado por una persona.",
        "no_link": "El enlace se añade al publicar el artículo.",
    },
    "en": {
        "brand": "Inspiring News",
        "brand_devastating": "Devastating News",
        "source": "Source",
        "sources": "Sources",
        "checked": "Checked",
        "checked_line": "{judged} of {total} claims of the original article checked",
        "not_checked": "Not checked",
        "read_more": "Read the full article",
        "link_in_bio": "Link in bio",
        "tap_link": "Tap the link",
        "swipe": "Swipe",
        "ai": "Written with AI ({models}).",
        "ai_edited": "Written with AI ({models}) and edited by a person.",
        "no_link": "The link is added when the article is published.",
    },
    "ca": {
        "brand": "Inspiring News",
        "brand_devastating": "Devastating News",
        "source": "Font",
        "sources": "Fonts",
        "checked": "Verificat",
        "checked_line": "{judged} de {total} afirmacions de l'article original, verificades",
        "not_checked": "Sense verificar",
        "read_more": "Llegeix l'article complet",
        "link_in_bio": "Enllaç a la bio",
        "tap_link": "Toca l'enllaç",
        "swipe": "Llisca",
        "ai": "Escrit amb IA ({models}).",
        "ai_edited": "Escrit amb IA ({models}) i editat per una persona.",
        "no_link": "L'enllaç s'afegeix en publicar l'article.",
    },
}

# What the reader's verdicts count as judged; NOT_CHECKED is neither.
JUDGED = {"TRUE", "PARTIALLY_TRUE", "FALSE", "MISLEADING"}


@dataclass
class Point:

    text: str

    # The domains of the sources the sentence cited, in its order.
    sources: list[str] = field(default_factory=list)


@dataclass
class PackageContent:

    language: str

    edition: str

    title: str

    subtitle: str

    points: list[Point]

    link: str | None

    disclosure: str

    hashtags: list[str]

    # Every source's domain, in the draft's order, once each.
    source_domains: list[str]

    # How many of the analysed article's claims the pipeline judged, of how many.
    judged: int

    total_checks: int

    words: dict[str, str]

    @property
    def brand(self) -> str:

        return self.words["brand_devastating" if self.edition == "devastating" else "brand"]


def content_hash(draft: ArticleDraft) -> str:

    text = "\n\x1f".join((draft.content.title, draft.content.subtitle, draft.content.body))

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def public_link(draft: ArticleDraft, site_url: str | None) -> str | None:
    """The story's public address, when it is published and the site's address is known."""

    if draft.status != "published" or not site_url:
        return None

    return site_url.rstrip("/") + public_path(draft.id)


def read(draft: ArticleDraft, site_url: str | None = None) -> PackageContent:

    words = TEXT.get(draft.language, TEXT["en"])
    lexicon = writing_lexicon_for(draft.language)

    domains = [source.domain for source in draft.sources]
    texts = {number: source.excerpt for number, source in enumerate(draft.sources, start=1) if source.excerpt}

    points: list[Point] = []

    # Factual sentences first, in the body's order, then the rest: a card
    # is worth a figure or a finding more than a transition.
    sentences = grounding.body_sentences(draft.content.body)
    ordered = [s for s in sentences if grounding.is_factual(s, lexicon)] + [
        s for s in sentences if not grounding.is_factual(s, lexicon)
    ]

    for sentence in ordered:

        text = plain_sentence(sentence)

        if len(text) > MAX_POINT_CHARS or len(text.split()) < MIN_POINT_WORDS:
            continue

        cited = []
        for number in grounding.citations(sentence):
            if 1 <= number <= len(domains) and domains[number - 1] not in cited:
                cited.append(domains[number - 1])

        # Uncited, but a source says it (the review's own lookup,
        # grounding.in_source): that source is named, as the review asks
        # the draft to cite it.
        if not cited:
            number = grounding.source_saying(sentence, texts, draft.language)
            if number is not None:
                cited.append(domains[number - 1])

        points.append(Point(text=text, sources=cited))

    # Back in the body's order: the story reads in the order it was written.
    position = {plain_sentence(s): i for i, s in enumerate(sentences)}
    points.sort(key=lambda point: position.get(point.text, 0))

    story = PublishedStory.of(draft, draft.updated_at or "")
    models = ", ".join(story.disclosure.models) or "?"
    disclosure = (words["ai_edited"] if story.disclosure.human_edited else words["ai"]).format(models=models)

    judged = sum(1 for check in draft.fact_checks if check.verdict.upper() in JUDGED)

    return PackageContent(
        language=draft.language,
        edition=draft.edition or "positive",
        title=draft.content.title.strip(),
        subtitle=draft.content.subtitle.strip(),
        points=points,
        link=public_link(draft, site_url),
        disclosure=disclosure,
        hashtags=hashtags([*draft.metadata.tags, *draft.metadata.keywords, draft.metadata.topic or ""]),
        source_domains=list(dict.fromkeys(domains)),
        judged=judged,
        total_checks=len(draft.fact_checks),
        words=words,
    )


def plain_sentence(sentence: str) -> str:
    """A body sentence as a card shows it: no citations, no Markdown, single spaces."""

    text = grounding.plain(sentence)

    return " ".join(text.split())


def hashtags(terms: list[str]) -> list[str]:
    """
    #CamelCase tags from the draft's own tags and keywords, accents kept
    (Instagram and TikTok both take them), punctuation out, once each
    ignoring case, at most MAX_HASHTAGS.
    """

    tags: list[str] = []
    seen: set[str] = set()

    for term in terms:

        words = re.findall(r"\w+", unicodedata.normalize("NFC", term or ""))
        tag = "".join(word[:1].upper() + word[1:] for word in words if not word.isdigit() or len(words) > 1)

        if len(tag) < 3 or tag.casefold() in seen:
            continue

        seen.add(tag.casefold())
        tags.append("#" + tag)

        if len(tags) >= MAX_HASHTAGS:
            break

    return tags


def caption(content: PackageContent, points: int, link_line: str | None) -> str:
    """
    The text posted with the media: headline, standfirst, a few points
    with who said each, where to read it, the sources, the AI disclosure
    and the hashtags - cut at CAPTION_LIMIT by dropping points, never
    mid-sentence.
    """

    def build(count: int) -> str:

        parts = [content.title]

        if content.subtitle:
            parts.append(content.subtitle)

        for point in content.points[:count]:
            said = f" ({content.words['source']}: {', '.join(point.sources)})" if point.sources else ""
            parts.append(f"• {point.text}{said}")

        if link_line:
            parts.append(link_line)

        if content.source_domains:
            parts.append(f"{content.words['sources']}: {', '.join(content.source_domains)}")

        parts.append(content.disclosure)

        if content.hashtags:
            parts.append(" ".join(content.hashtags))

        return "\n\n".join(parts)

    for count in range(points, -1, -1):

        text = build(count)

        if len(text) <= CAPTION_LIMIT:
            return text

    return build(0)[:CAPTION_LIMIT]
