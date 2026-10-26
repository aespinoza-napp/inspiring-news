"""
What a trend is, once read: a name, how much it is spreading, when it
started, and the articles that explain it (docs/decisions/trends.md).

A trend is not an article. It is a question - why is everyone talking
about this? - and the answer is in the news that explains it, so the
pipeline never analyses a trend: it analyses its articles, as it would
any other candidate, and the trend travels with them as a card.
"""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime


def _iso(value: datetime | None) -> str | None:

    return value.isoformat(timespec="seconds") if value else None


def trend_id(signal: str, name: str) -> str:
    """
    The same trend from the same signal gets the same id on every read:
    Google lists "ester expósito" again an hour later, and both reads are
    one trend. Accents and case folded, so "Expósito" is "exposito".
    """

    decomposed = unicodedata.normalize("NFKD", name.lower())
    folded = " ".join("".join(char for char in decomposed if not unicodedata.combining(char)).split())

    return hashlib.sha1(f"{signal}|{folded}".encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True)
class TrendArticle:
    """One page that explains a trend."""

    url: str

    title: str | None = None

    # The outlet as the signal names it ("EL PAÍS"); None when it does not.
    outlet: str | None = None

    snippet: str | None = None

    # The page's own time, when the signal or the search gave one.
    published: datetime | None = None

    # "signal": the signal attached it (Google's news items, a post's
    # link); "search": found by searching the trend's name.
    found_by: str = "signal"

    def to_dict(self) -> dict:

        return {
            "url": self.url,
            "title": self.title,
            "outlet": self.outlet,
            "snippet": self.snippet,
            "publishedAt": _iso(self.published),
            "foundBy": self.found_by,
        }


@dataclass
class Trend:

    id: str

    name: str

    # The signal's id and name; "seed" for one a person typed.
    signal: str

    signal_name: str

    # The language it is searched and screened in; None for a seed, which
    # is searched in any.
    language: str | None

    # Its place in the signal's feed, 1 first: Google lists the rising
    # searches newest first, a subreddit's top posts most voted first.
    position: int

    # Google's approximate searches ("2000+" -> 2000); None elsewhere.
    traffic: int | None = None

    started_at: datetime | None = None

    # Where a person can see the trend itself: Google's explore page, a
    # Reddit thread, the outlet's page.
    link: str | None = None

    articles: list[TrendArticle] = field(default_factory=list)

    # A TikTok video a person gave (services/trends/seeds.py): provider,
    # id, url, and the caption and author when oEmbed gave them.
    video: dict | None = None

    # Typed by a person rather than read from a signal.
    seed: bool = False

    # The signal says its items are chosen for being good news.
    positive: bool = False

    # What went wrong or was left out on the way, for the round to show.
    notes: list[str] = field(default_factory=list)

    def card(self) -> dict:
        """What a candidate carries of its trend: everything but the other articles."""

        return {
            "id": self.id,
            "name": self.name,
            "signal": self.signal,
            "signalName": self.signal_name,
            "position": self.position,
            "traffic": self.traffic,
            "startedAt": _iso(self.started_at),
            "link": self.link,
            "video": self.video,
            "seed": self.seed,
            "positive": self.positive,
        }

    def to_dict(self) -> dict:

        return {
            **self.card(),
            "language": self.language,
            "articles": [article.to_dict() for article in self.articles],
            "notes": list(self.notes),
        }
