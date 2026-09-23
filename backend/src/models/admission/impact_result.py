


from pydantic import BaseModel


class ImpactResult(BaseModel):

    passed: bool

    score: float

    reasons: list[str]
