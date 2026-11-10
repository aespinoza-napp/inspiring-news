from typing import Optional

from pydantic import BaseModel, Field


class CorrectionMetric(BaseModel):

    score: float

    summary: str

    issues: list[str] = Field(default_factory=list)

    # The score the review's model gave, when the review set it aside
    # because it contradicted the model's own summary (draft_reviewer.py,
    # `follow_the_check`): kept so nobody has to take the override on trust.
    # None when the model's number is the score.
    reported: Optional[float] = None
