from pydantic import BaseModel

from typing import Dict

class Claim(BaseModel):

    text: str

    entities: dict[str, list[str]]

    confidence: float