"""
A trend a person brings: a hashtag, a few words, a TikTok link, or a
news link that explains it (docs/decisions/trends.md, "The signals").

The only way TikTok enters the system. Its own trend listing is not read
- on 2026-10-26 it answered `{"code":40101,"msg":"no permission"}` without
a signed-in session, and its terms forbid scraping - so a person who saw
a trend there types it here. A hashtag becomes a news search for the
articles that explain it. A TikTok link is kept as the trend's video,
which a published story can show through TikTok's own player (oEmbed:
public, no key, read once for the caption), and never fetched as a page.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# A seed is a line, not an essay.
SEED_CHARS = 300

# Words of a caption or a line used as the trend's name, which is also its
# search: past this a name is a sentence (the writer's related news cuts a
# headline at the same length).
NAME_WORDS = 14

TIKTOK_LINK = re.compile(r"https?://(?:www\.|m\.|vm\.|vt\.)?tiktok\.com/\S+", re.IGNORECASE)

ANY_LINK = re.compile(r"https?://\S+", re.IGNORECASE)

HASHTAG = re.compile(r"#(\w+)")

# The id in a full video link: tiktok.com/@user/video/6718335390845095173.
VIDEO_ID = re.compile(r"/video/(\d+)")

# Tags that say a video wants reach, not what it is about.
REACH_TAGS = {"fyp", "foryou", "foryoupage", "parati", "paratii", "viral", "trending", "xyzbca", "tiktok"}

_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


class SeedError(ValueError):
    """The seed names nothing to look for."""


@dataclass
class Seed:

    # What is searched for: the hashtags as words, or the words typed.
    name: str

    tiktok: str | None = None

    # Other links typed with it: pages that explain the trend.
    links: list[str] = field(default_factory=list)


def hashtag_words(tag: str) -> str:
    """#FarmearAura -> "Farmear Aura"; #farmear_aura -> "farmear aura"; #farmearaura stays one word."""

    return " ".join(_CAMEL.sub(" ", tag.replace("_", " ")).split())


def name_from(text: str) -> str:
    """The words worth searching for in a line or a caption: its hashtags if it has any, else its words."""

    tags = [tag for tag in HASHTAG.findall(text) if tag.lower() not in REACH_TAGS]

    if tags:
        words = " ".join(hashtag_words(tag) for tag in tags).split()
    else:
        words = HASHTAG.sub(" ", text).split()

    return " ".join(words[:NAME_WORDS])


def parse_seed(text: str) -> Seed:
    """
    What a person typed, taken apart: a TikTok link, other links, and the
    words to search for. Raises SeedError when it is empty.
    """

    text = (text or "").strip()[:SEED_CHARS]

    if not text:
        raise SeedError("Type a hashtag, a few words or a TikTok link.")

    links = ANY_LINK.findall(text)
    tiktok = next((link for link in links if TIKTOK_LINK.match(link)), None)
    others = [link for link in links if link != tiktok]

    words = ANY_LINK.sub(" ", text)

    return Seed(name=name_from(words), tiktok=tiktok, links=others)


def video_id(link: str) -> str | None:
    """The numeric id in a full TikTok video link; None in a short one (vm.tiktok.com/...)."""

    found = VIDEO_ID.search(link or "")

    return found.group(1) if found else None
