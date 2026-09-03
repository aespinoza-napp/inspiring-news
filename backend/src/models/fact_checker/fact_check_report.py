from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.models.fact_checker.fact_check import FactCheck, Verdict


class FactCheckReport(BaseModel):

    article_id: str

    checked_at: datetime = Field(default_factory=datetime.now)

    validation_passed: bool

    skipped_reason: Optional[str] = None

    topic_ok: bool = True

    positive_ok: bool = True

    impact_score: float = 0.0

    impact_reasons: list[str] = Field(default_factory=list)

    duplicate: bool = False

    claims_total: int = 0

    claims_selected: int = 0

    claim_checks: list[FactCheck] = Field(default_factory=list)

    overall_verdict: Verdict = Verdict.UNVERIFIED

    overall_confidence: float = 0.0
