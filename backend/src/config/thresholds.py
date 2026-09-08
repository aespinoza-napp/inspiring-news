"""
The pipeline's tunable thresholds, resolved per run.

Two models, deliberately:

- `PipelineThresholds` is the *effective* set - every field has a
  concrete value, defaulted from `settings` (i.e. from the environment).
  Pipeline components read from an instance of this and never from
  `settings` directly.
- `ThresholdOverrides` is the *request* shape - every field is optional.
  It is what a caller sends to change one or two knobs for a single run
  without having to restate the rest.

`PipelineThresholds.resolve(overrides)` merges the two: whatever the
caller set wins, everything else falls back to the environment default.

Why not read `settings` at the point of use? Because the components are
long-lived singletons (see container.py) shared by every request, so a
per-run value cannot live on the instance. It has to be passed in at
call time, which is what every `validate()`/`process()`/`select()`
signature below now accepts.

Weights (RANKING_*, CONFIDENCE_*) are deliberately *not* here: each
group has to sum to 1.0, and letting a request set one member of a group
independently would silently produce a scoring function that no longer
normalises. Those stay environment-only.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from src.config.settings import settings


class PipelineThresholds(BaseModel):
    """
    The effective thresholds for one pipeline run. Defaults come from
    `settings`, so an unmodified run behaves exactly as the environment
    configures it.
    """

    model_config = {"frozen": True}

    # ---- enrichment ---------------------------------------------------

    # Minimum cosine similarity for a topic to be predicted at all.
    topic_classifier_threshold: float = Field(
        default_factory=lambda: settings.TOPIC_CLASSIFIER_THRESHOLD,
        ge=0.0,
        le=1.0,
    )

    # GLiNER's confidence floor for a named entity.
    entity_threshold: float = Field(
        default_factory=lambda: settings.ENTITY_THRESHOLD,
        ge=0.0,
        le=1.0,
    )

    # Minimum check-worthiness score for a sentence to become a Claim.
    claim_min_confidence: float = Field(
        default_factory=lambda: settings.CLAIM_MIN_CONFIDENCE,
        ge=0.0,
        le=1.0,
    )

    # ---- extraction ---------------------------------------------------

    # Shortest extracted body (characters) accepted as a real article.
    min_body_length: int = Field(
        default_factory=lambda: settings.MIN_BODY_LENGTH,
        ge=0,
    )

    # ---- admission filter ---------------------------------------------

    # An article needs at least one topic above this to be on-topic.
    topic_min_confidence: float = Field(
        default_factory=lambda: settings.TOPIC_MIN_CONFIDENCE,
        ge=0.0,
        le=1.0,
    )

    # Minimum normalised positive-impact score to clear admission.
    positive_impact_min_score: float = Field(
        default_factory=lambda: settings.POSITIVE_IMPACT_MIN_SCORE,
        ge=0.0,
        le=1.0,
    )

    # At/above this similarity to a stored article, it is a duplicate.
    duplicate_threshold: float = Field(
        default_factory=lambda: settings.DUPLICATE_THRESHOLD,
        ge=0.0,
        le=1.0,
    )

    # At/above this, a stored article is "related" - not a duplicate, but
    # usable as internal corroborating evidence.
    relatedness_threshold: float = Field(
        default_factory=lambda: settings.RELATEDNESS_THRESHOLD,
        ge=0.0,
        le=1.0,
    )

    # ---- fact-checking ------------------------------------------------

    max_claims_per_article: int = Field(
        default_factory=lambda: settings.MAX_CLAIMS_PER_ARTICLE,
        ge=1,
    )

    # Two claims at/above this similarity count as the same claim.
    claim_dedup_threshold: float = Field(
        default_factory=lambda: settings.CLAIM_DEDUP_THRESHOLD,
        ge=0.0,
        le=1.0,
    )

    max_evidence_per_claim: int = Field(
        default_factory=lambda: settings.MAX_EVIDENCE_PER_CLAIM,
        ge=1,
    )

    # Below this many evidence items, the verdict is forced to UNVERIFIED
    # regardless of what the LLM says.
    min_evidence_for_verdict: int = Field(
        default_factory=lambda: settings.MIN_EVIDENCE_FOR_VERDICT,
        ge=0,
    )

    # ------------------------------------------------------------------

    @classmethod
    def resolve(
        cls,
        overrides: Optional["ThresholdOverrides"] = None,
    ) -> "PipelineThresholds":
        """
        The environment defaults, with any field the caller actually set
        applied on top. `None` (no overrides at all) yields the defaults.
        """

        if overrides is None:
            return cls()

        return cls(**overrides.model_dump(exclude_none=True))

    def overridden_from_defaults(self) -> dict[str, float | int]:
        """
        Only the fields that differ from the environment defaults. Used
        to stamp a run's lineage without recording a dozen values that
        are just "whatever .env says" - and so a record makes it obvious
        at a glance that a run was tuned.
        """

        defaults = PipelineThresholds()

        return {
            name: value
            for name, value in self.model_dump().items()
            if value != getattr(defaults, name)
        }


class ThresholdOverrides(BaseModel):
    """
    Per-run overrides. Every field is optional: send only the knobs you
    want to change, the rest fall back to the environment defaults.

    Field names and bounds mirror PipelineThresholds exactly - a test
    asserts that, so the two cannot drift apart.
    """

    model_config = {"extra": "forbid"}

    topic_classifier_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    entity_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    claim_min_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)

    min_body_length: Optional[int] = Field(None, ge=0)

    topic_min_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    positive_impact_min_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    duplicate_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    relatedness_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)

    max_claims_per_article: Optional[int] = Field(None, ge=1)
    claim_dedup_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_evidence_per_claim: Optional[int] = Field(None, ge=1)
    min_evidence_for_verdict: Optional[int] = Field(None, ge=0)
