from pydantic import BaseModel


class FactCheck(BaseModel):

    verdict: str

    explanation: str

    confidence: float