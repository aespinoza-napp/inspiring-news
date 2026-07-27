from pydantic import BaseModel

from src.models.claim import Claim


class NLPResult(BaseModel):

    keywords: list[str]

    entities: list[str]

    category: str

    sentiment: float

    claims: list[Claim]

    embedding: list[float]