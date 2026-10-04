from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ExtractionResult(BaseModel):
    source_id: str
    title: Optional[str] = None
    body: str

    summary: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    lead_image: Optional[str] = None

    # The publication time to the minute, when the page states one
    # (article:published_time, JSON-LD datePublished...). `published_at`
    # stays the date everything else reads; this is what the freshness
    # report measures reception against when no feed gave a time.
    published_time: Optional[datetime] = None