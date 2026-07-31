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