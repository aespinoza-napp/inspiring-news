from pydantic import BaseModel


class Claim(BaseModel):

    text: str

    confidence: float | None = None

    entities: list[str] = []