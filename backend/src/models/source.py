from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


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

    metadata: dict = Field(default_factory=dict)