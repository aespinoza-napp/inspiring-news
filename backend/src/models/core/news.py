from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field
from typing import Optional
from src.models.core.claim import Claim
from src.models.fact_checker.fact_check import FactCheck

class News(BaseModel):

    id: str = Field(default_factory=lambda: uuid4().hex)

    source_id: str

    url: str

    title: Optional[str] = None

    author: Optional[str] = None

    published_at: Optional[datetime] = None

    content: str

    image_url: Optional[str] = None

    claims: list[Claim] = []

    fact_checks: list[FactCheck] = []

    metadata: dict = {}

    sentiment: Optional[float] = None