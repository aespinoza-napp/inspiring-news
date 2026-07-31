from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EvidenceOrigin(str, Enum):
    WEB = "web"
    INTERNAL = "internal"


class Evidence(BaseModel):

    url: str

    title: str

    snippet: str = ""

    content: Optional[str] = None

    source_name: Optional[str] = None

    source_reliability: Optional[float] = None

    published_at: Optional[datetime] = None

    retrieved_at: datetime = Field(default_factory=datetime.now)

    origin: EvidenceOrigin

    relevance_score: Optional[float] = None
