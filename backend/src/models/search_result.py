from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime

from src.models.source import NewsSource


class SearchResult(BaseModel):
    source: NewsSource
    url: HttpUrl
    title: str
    published_at: datetime | None = None