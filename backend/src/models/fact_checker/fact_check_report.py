from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.models.core.claim import RejectedClaim
from src.models.fact_checker.fact_check import FactCheck, Verdict
from src.models.fact_checker.pipeline_stage import PipelineStage


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

    failed_stage: Optional[PipelineStage] = None

    unselected_claims: list[RejectedClaim] = Field(default_factory=list)

    claims_total: int = 0

    claims_selected: int = 0

    claim_checks: list[FactCheck] = Field(default_factory=list)

    overall_verdict: Verdict = Verdict.UNVERIFIED

    overall_confidence: float = 0.0

    # "How much could be checked" apart from "what was found" (Sep 21
    # audit). overall_verdict is worst-claim-wins over every claim, so one
    # UNVERIFIED outweighs any number of TRUE and a search outage reads
    # like a finding. found_verdict is the worst among the claims that
    # reached a definitive verdict (None when none did); the three counts
    # say how the rest ended. overall_verdict keeps its meaning: the
    # reader's admission and the thesis's numbers rest on it.
    found_verdict: Optional[Verdict] = None

    claims_judged: int = 0

    claims_unverified: int = 0

    claims_not_checked: int = 0

    # True when the article yielded fewer anchor claims than
    # anchor_claims_min. The verdict still stands for what was checked,
    # but it rests on one assertion rather than on the two-to-four an
    # article's credibility is supposed to be judged by - which is a
    # caveat on the whole report, not on any single claim.
    below_anchor_floor: bool = False
