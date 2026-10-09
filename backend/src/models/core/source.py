from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator

from src.config.topics import TOPIC_GROUPS


class SourceType(str, Enum):
    NEWS = "news"
    BLOG = "blog"
    GOVERNMENT = "government"
    ACADEMIC = "academic"
    SOCIAL = "social"


class JsonFeed(BaseModel):
    """
    Where a JSON listing of a source's articles keeps them: the items, and
    in each its link, title and time, by key. WHO's news API on
    2026-10-09: items under "value", the link in "ItemDefaultUrl" (a path,
    after https://www.who.int/news/item), the title in "Title", the time in
    "PublicationDateAndTime" - while its RSS feed's newest item was from
    February.
    """

    url: HttpUrl

    # Dotted path to the list of items; "" when the document is the list.
    items: str = ""

    link: str

    # Put before a link that is only a path.
    link_prefix: Optional[str] = None

    title: str

    summary: Optional[str] = None

    # An ISO 8601 time.
    published: Optional[str] = None


class NewsSource(BaseModel):
    """
    Represents a news source or publisher.
    """

    id: str = Field(description="Unique identifier, e.g. cnn")

    name: str

    base_url: HttpUrl

    source_type: SourceType = SourceType.NEWS

    rss_url: Optional[HttpUrl] = None

    # A Google News sitemap: every article of the last two days with its
    # title and publication time, for publishers whose feed has died
    # (CNN's stopped in 2024). Read when the feed finds nothing.
    news_sitemap_url: Optional[HttpUrl] = None

    # A JSON listing of articles (JsonFeed), for publishers with neither
    # a live feed nor a news sitemap (WHO). Read when the feed finds
    # nothing.
    json_feed: Optional[JsonFeed] = None

    search_url: Optional[str] = None

    language: str = "en"

    country: Optional[str] = None

    reliability_index: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Estimated editorial reliability.",
    )

    enabled: bool = True

    requires_javascript: bool = False

    tags: list[str] = Field(default_factory=list)

    # Which of the five topic groups (src/config/topics.py TOPIC_GROUPS)
    # this source is worth reading for. Ingestion discovers only from the
    # sources of the groups asked for, so a generalist names the groups it
    # has real sections for, not all five. Free-form `tags` stay as they
    # were; these are the ones the code reads.
    groups: list[str] = Field(default_factory=list)

    # A group -> the section paths that cover it on this site, for the
    # topic-page step to read instead of guessing them from topic names.
    # Smithsonian's Environment candidates all came from a guessed /food/
    # on 2026-10-09 - food history and travel, three of the round's first
    # six - while /climate/, /nature/ and /energy/ were 404s; its section
    # is /science-nature/.
    sections: dict[str, list[str]] = Field(default_factory=dict)

    # An outlet that publishes only positive news, chosen by its own
    # editors (Good News Network, Positive News, Reasons to be Cheerful).
    # Discovery's mission screen leaves its items alone: on 2026-10-06 it
    # would have dropped Good News Network's ex-prisoners-as-firefighters
    # jobs story as "crime" (src/services/selection/mission_screen.py).
    positive_editorial: bool = False

    metadata: dict = Field(default_factory=dict)

    @field_validator("sections")
    @classmethod
    def _known_section_groups(cls, sections: dict[str, list[str]]) -> dict[str, list[str]]:

        cls._known_groups(list(sections))

        return sections

    @field_validator("groups")
    @classmethod
    def _known_groups(cls, groups: list[str]) -> list[str]:

        unknown = sorted(set(groups) - set(TOPIC_GROUPS))

        if unknown:
            raise ValueError(
                f"unknown topic group(s) {', '.join(unknown)}; "
                f"expected some of {', '.join(TOPIC_GROUPS)}"
            )

        return groups
