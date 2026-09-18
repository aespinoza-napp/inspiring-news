from pydantic import BaseModel, Field


class ClaimFacts(BaseModel):
    """
    The verifiable components of a claim, kept as data rather than only
    as scoring signals.

    ClaimExtractor already detects all of these to decide whether a
    sentence is check-worthy; it used to throw them away immediately
    afterwards. They are retained because they are the most
    discriminative terms available when building a search query - a
    figure or a year pins an event far more tightly than the surrounding
    prose does - and because the UI shows what was actually being
    checked.
    """

    figures: list[str] = Field(default_factory=list)

    dates: list[str] = Field(default_factory=list)

    quotes: list[str] = Field(default_factory=list)


class Claim(BaseModel):

    text: str

    entities: dict[str, list[str]]

    confidence: float

    facts: ClaimFacts = Field(default_factory=ClaimFacts)

    # How much the sentence reads as opinion/interpretation rather than a
    # checkable assertion. Scored for every candidate sentence; those
    # above the run's opinion_max_score never become claims at all.
    opinion_score: float = 0.0

    # How load-bearing this claim is for the article's credibility, set
    # by ClaimSelector. None until selection has run.
    anchor_score: float | None = None


class RejectedClaim(BaseModel):
    """An extracted claim that never reached verification."""

    text: str

    confidence: float

    reason: str
