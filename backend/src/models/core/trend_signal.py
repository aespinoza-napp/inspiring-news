"""
A trend signal: a public feed that says what is spreading right now
(docs/decisions/trends.md).

Not a news source. A source is read for its articles and rated for its
reliability, by domain, one source per domain. A signal is read for what
people are searching for, voting up or sharing, and is never evidence:
Google Trends is one domain (trends.google.com) for every country, and
its "articles" are other outlets' pages. So signals live in their own
folder, data/trends/, with their own model.

Every signal is a public feed read with no key and no login: the trends
work is free by rule (docs/goals.md, "Trends"). TikTok is not one of them
- its own trend listing needs a signed session and its terms forbid
scraping it - and reaches the system as the searches and news it causes,
or as a hashtag or link a person types (services/trends/seeds.py).
"""

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

from src.config.lexicons import SUPPORTED_LANGUAGES

# How a signal's feed is read (services/trends/readers.py):
#
# - google_trends: Google Trends' "Trending now" RSS, one item per rising
#   search, with its approximate searches and the news articles Google
#   attaches to it.
# - ranked_feed: an ordinary RSS or Atom feed whose order is the signal -
#   a subreddit's top posts of the day, a viral outlet's newest. Each item
#   is one trend, and its article is the page the item links to.
SignalKind = Literal["google_trends", "ranked_feed"]


class TrendSignal(BaseModel):

    id: str = Field(description="Unique identifier, e.g. google_trends_es")

    name: str

    kind: SignalKind

    url: HttpUrl

    # The language its trends are searched and screened in. One with a
    # lexicon (CLAUDE.md, invariant 8): a third language would be scored
    # as English.
    language: str

    # ISO 3166 code for a country's trends (Google's `geo`); None for a
    # feed that has no country.
    country: str | None = None

    # Its items are already chosen for being good news, by a community
    # (r/UpliftingNews) or an outlet's editors (Upworthy). Shown as such on
    # /discover. Not exempt from the mission screen: on 2026-10-26
    # r/UpliftingNews also carried an election result and a police story.
    positive: bool = False

    # Its items lean to bad news (r/worldnews): read only by the
    # Devastating edition (src/config/editions.py), as a `positive` one is
    # read only by the positive edition. Neither: both read it - Google's
    # rising searches are whatever people search.
    devastating: bool = False

    enabled: bool = True

    def belongs_to(self, edition: str) -> bool:
        """Whether a round of `edition` reads this signal."""

        return not self.devastating if edition == "positive" else not self.positive

    @field_validator("language")
    @classmethod
    def _has_a_lexicon(cls, language: str) -> str:

        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Signal language {language!r} has no lexicon (src/config/lexicons.py); "
                f"expected one of {sorted(SUPPORTED_LANGUAGES)}."
            )

        return language
