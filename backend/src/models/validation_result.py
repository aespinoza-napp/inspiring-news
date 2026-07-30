


from pydantic import BaseModel


class ValidationResult(BaseModel):

    passed: bool

    score: float

    reasons: list[str]
