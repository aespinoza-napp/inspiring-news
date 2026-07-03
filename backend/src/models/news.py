from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field
from typing import Optional
from src.models.claim import Claim
from src.models.fact_check import FactCheck

class News(BaseModel):

    id: str = Field(default_factory=lambda: uuid4().hex)

    title: str

    source_id: str

    url: str

    published_at: datetime

    content: str

    claims: list[Claim] = []

    fact_checks: list[FactCheck] = []

    metadata: dict = {}
    sentiment: Optional[float] = None