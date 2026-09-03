from pydantic import BaseModel

from typing import Dict

class Claim(BaseModel):

    text: str

    entities: dict[str, list[str]]

    confidence: float


class RejectedClaim(BaseModel):
    """An extracted claim that never reached verification."""

    text: str

    confidence: float

    reason: str