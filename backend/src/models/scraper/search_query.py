from pydantic import BaseModel, Field
from datetime import datetime

from src.models.core.source import NewsSource

class SearchQuery(BaseModel):
    keywords: list[str]
    source: NewsSource | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    language: str | None = None
    max_results: int = 20