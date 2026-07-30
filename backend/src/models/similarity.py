from dataclasses import dataclass
from typing import List, Optional
from pydantic import BaseModel

class SimilarArticle(BaseModel):

    id: str

    similarity: float

    title: Optional[str] = None

    url: Optional[str] = None

    source_id: Optional[str] = None