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


class NewsSource(BaseModel):
    """
    Represents a news source or publisher.
    """

    id: str = Field(description="Unique identifier, e.g. cnn")

    name: str

    base_url: HttpUrl

    source_type: SourceType = SourceType.NEWS

    rss_url: Optional[HttpUrl] = None

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

    metadata: dict = Field(default_factory=dict)

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
