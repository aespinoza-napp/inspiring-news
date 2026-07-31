from pydantic import BaseModel, Field


class CorrectionMetric(BaseModel):

    score: float

    summary: str

    issues: list[str] = Field(default_factory=list)
