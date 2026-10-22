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

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from src.config.settings import settings

# The questions a claim's first search asks, in the order they are
# planned (services/fact_checker/retrieval/query_builder.py, QueryKind -
# held equal to it by a test; named here so config imports no service).
SEARCH_QUERY_KINDS = ("anchor", "proposition", "refutation")


# Named sets of per-run thresholds an environment can take as its defaults
# with one setting, FACT_CHECK_PROFILE (docs/decisions/performance.md, "The
# 20-second fact-check"). A field a caller sets still wins; a field neither
# names falls back to its setting as always. `thorough` names nothing: the
# defaults as they were. `fast` and `fast_snippets` are the contest's
# entries C and D, held equal to data/evaluation/thresholds/fast.json and
# fast_snippets.json by a test, so a profile and its harness preset cannot
# drift apart.
FACT_CHECK_PROFILES: dict[str, dict] = {
    "thorough": {},
    "fast": {
        "verifier_answer": "compact",
        "evidence_prerank": "lexical",
        "ranking_text": "passages",
        "query_kinds": ("anchor", "proposition"),
        "max_evidence_per_claim": 3,
        "verifier_excerpt_chars": 400,
        "claim_deadline_seconds": 30,
    },
    "fast_snippets": {
        "verifier_answer": "compact",
        "evidence_prerank": "lexical",
        "ranking_text": "passages",
        "query_kinds": ("anchor", "proposition"),
        "max_evidence_per_claim": 3,
        "verifier_excerpt_chars": 400,
        "claim_deadline_seconds": 30,
        "fetch_evidence_pages": False,
    },
}


def _query_kinds(value) -> tuple[str, ...]:
    """
    At least one known kind, in planning order, each once. A typo must
    fail the request: silently dropped, it would turn an ablation into
    a different one than the run says it was.
    """

    unknown = [kind for kind in value if kind not in SEARCH_QUERY_KINDS]

    if unknown:
        raise ValueError(f"unknown query kind(s) {unknown}; known: {list(SEARCH_QUERY_KINDS)}")

    if not value:
        raise ValueError("at least one query kind is needed: a claim with no query is never searched")

    return tuple(kind for kind in SEARCH_QUERY_KINDS if kind in value)


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

    # Above this opinion score, a sentence is treated as interpretation
    # rather than a checkable assertion and never becomes a Claim. There
    # is no evidence that can confirm or refute "a hopeful step for the
    # sector", so putting one through retrieval only spends a search and
    # an LLM call to arrive at UNVERIFIED.
    opinion_max_score: float = Field(
        default_factory=lambda: settings.OPINION_MAX_SCORE,
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

    # Whether low objectivity / strong negative sentiment reject an
    # article outright, rather than only costing it score.
    positive_impact_hard_fail_enabled: bool = Field(
        default_factory=lambda: settings.POSITIVE_IMPACT_HARD_FAIL_ENABLED,
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

    # The anchor band: how many load-bearing claims to verify. This
    # replaced max_claims_per_article outright rather than sitting beside
    # it - two caps on the same list is a knob that silently does
    # nothing, and the selector now ranks by how load-bearing a claim is
    # rather than by sentence-level check-worthiness, so the old name
    # described the wrong thing as well as the wrong number.
    anchor_claims_min: int = Field(
        default_factory=lambda: settings.ANCHOR_CLAIMS_MIN,
        ge=1,
    )

    anchor_claims_max: int = Field(
        default_factory=lambda: settings.ANCHOR_CLAIMS_MAX,
        ge=1,
    )

    # How many distinct domains must back a claim before it counts as
    # corroborated. Raw evidence count cannot do this job: five
    # syndications of one wire story are one source.
    min_independent_domains: int = Field(
        default_factory=lambda: settings.MIN_INDEPENDENT_DOMAINS,
        ge=1,
    )

    # Two claims at/above this similarity count as the same claim.
    claim_dedup_threshold: float = Field(
        default_factory=lambda: settings.CLAIM_DEDUP_THRESHOLD,
        ge=0.0,
        le=1.0,
    )

    # How many search hits to ask SearXNG for per claim, before the
    # pre-rank funnel cuts them down to max_evidence_per_claim. Tunable
    # because widening recall is the first thing to try when a claim
    # comes back UNVERIFIED for lack of evidence.
    evidence_fetch_candidates: int = Field(
        default_factory=lambda: settings.EVIDENCE_FETCH_CANDIDATES,
        ge=1,
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

    # How much a source has to actually address the assertion - not just
    # its subject - to be allowed into the evidence set at all. Anything
    # below is cut at ranking with a reason, and therefore cannot be
    # counted, cited or corroborated.
    #
    # Per-run because it is the knob that trades a confident wrong answer
    # for an honest UNVERIFIED: raise it when a run is citing sources that
    # are merely on-topic, lower it when claims come back unverified with
    # plausible sources sitting in the cut list.
    evidence_min_pertinence: float = Field(
        default_factory=lambda: settings.EVIDENCE_MIN_PERTINENCE,
        ge=0.0,
        le=1.0,
    )

    # Which of the first search's queries are sent: the retrieval
    # ablation's switch (roadmap, Thesis priorities P1.1). Switching a
    # query kind off on the same frozen claims, in one window, measures
    # what it adds, which the versions in git cannot: they no longer run
    # on today's web. Always all three outside an experiment, so the
    # default is fixed here rather than read from the environment, and a
    # run with all three keeps the key it had before this switch existed
    # (evaluation/runner.py, keyed_thresholds). Order does not matter;
    # it is normalised to the planning order.
    query_kinds: tuple[str, ...] = Field(default=SEARCH_QUERY_KINDS)

    @field_validator("query_kinds")
    @classmethod
    def _known_query_kinds(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _query_kinds(value)

    @model_validator(mode="before")
    @classmethod
    def _profile_defaults(cls, values):
        """
        The environment's profile (FACT_CHECK_PROFILE) fills every field it
        names that the caller did not set. Read per instance, like every
        other default here, so a test or a long-lived process sees a
        changed setting.
        """

        profile = FACT_CHECK_PROFILES[settings.FACT_CHECK_PROFILE]

        if not profile or not isinstance(values, dict):
            return values

        return {**profile, **values}

    # The second look: when a claim's first verdict is UNVERIFIED, or its
    # confidence is below `second_look_below_confidence`, search again
    # with follow-up queries written from what the first verdict said was
    # missing, and judge the old and new evidence together. Per-run
    # because it costs a second search and two more model calls on the
    # claims it fires on, and because whether it helps is measured, not
    # assumed: on the tuning half first, then the test half.
    second_look_enabled: bool = Field(
        default_factory=lambda: settings.SECOND_LOOK_ENABLED,
    )

    second_look_below_confidence: float = Field(
        default_factory=lambda: settings.SECOND_LOOK_BELOW_CONFIDENCE,
        ge=0.0,
        le=1.0,
    )

    # What the verifier is shown of each source, and how much of it
    # (verification/excerpts.py): `head`, the page's first characters, or
    # `passages`, the sentences that carry the claim's terms. The model
    # reads its prompt at CPU speed, so this is most of a claim's time
    # (docs/decisions/performance.md). Per-run because it changes what
    # the model judges on, and whether it reads as well is measured on
    # the tuning half, like the second look.
    verifier_excerpt: Literal["head", "passages"] = Field(
        default_factory=lambda: settings.VERIFIER_EXCERPT,
    )

    verifier_excerpt_chars: int = Field(
        default_factory=lambda: settings.VERIFIER_EXCERPT_CHARS,
        ge=200,
        le=8000,
    )

    # The speed switches (settings.py has what each costs and saves).
    # Per-run because each changes what a verdict rests on - fewer
    # pages, chosen by words alone, judged on their passages, a shorter
    # answer - and whether that is worth the seconds is measured on the
    # tuning half, as the excerpt was: docs/decisions/performance.md.
    verifier_answer: Literal["full", "compact", "per_source"] = Field(
        default_factory=lambda: settings.VERIFIER_ANSWER,
    )

    # What the verifier is told a verdict means (settings.py has why).
    # Per-run because it changes the verdicts themselves, and whether it
    # judges better is measured by replaying one run's evidence
    # (evaluation/replay.py).
    verifier_rules: Literal["original", "stated"] = Field(
        default_factory=lambda: settings.VERIFIER_RULES,
    )

    evidence_prerank: Literal["embedding", "lexical"] = Field(
        default_factory=lambda: settings.EVIDENCE_PRERANK,
    )

    ranking_text: Literal["head", "passages"] = Field(
        default_factory=lambda: settings.RANKING_TEXT,
    )

    fetch_evidence_pages: bool = Field(
        default_factory=lambda: settings.FETCH_EVIDENCE_PAGES,
    )

    # A budget for one claim, not a ceiling on a shared service (those
    # are settings, invariant 12): it can only make a claim give up
    # sooner, never ask more of SearXNG, inference/ or the model than the
    # settings' own timeouts allow. 0 is no deadline.
    claim_deadline_seconds: int = Field(
        default_factory=lambda: settings.CLAIM_DEADLINE_SECONDS,
        ge=0,
        le=600,
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
    opinion_max_score: Optional[float] = Field(None, ge=0.0, le=1.0)

    min_body_length: Optional[int] = Field(None, ge=0)

    topic_min_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    positive_impact_min_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    positive_impact_hard_fail_enabled: Optional[bool] = Field(None)
    duplicate_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    relatedness_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)

    anchor_claims_min: Optional[int] = Field(None, ge=1)
    anchor_claims_max: Optional[int] = Field(None, ge=1)
    min_independent_domains: Optional[int] = Field(None, ge=1)
    evidence_fetch_candidates: Optional[int] = Field(None, ge=1)
    claim_dedup_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_evidence_per_claim: Optional[int] = Field(None, ge=1)
    min_evidence_for_verdict: Optional[int] = Field(None, ge=0)
    evidence_min_pertinence: Optional[float] = Field(None, ge=0.0, le=1.0)
    second_look_enabled: Optional[bool] = Field(None)
    second_look_below_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    query_kinds: Optional[tuple[str, ...]] = Field(None)
    verifier_excerpt: Optional[Literal["head", "passages"]] = Field(None)
    verifier_excerpt_chars: Optional[int] = Field(None, ge=200, le=8000)
    verifier_answer: Optional[Literal["full", "compact", "per_source"]] = Field(None)
    verifier_rules: Optional[Literal["original", "stated"]] = Field(None)
    evidence_prerank: Optional[Literal["embedding", "lexical"]] = Field(None)
    ranking_text: Optional[Literal["head", "passages"]] = Field(None)
    fetch_evidence_pages: Optional[bool] = Field(None)
    claim_deadline_seconds: Optional[int] = Field(None, ge=0, le=600)

    @field_validator("query_kinds")
    @classmethod
    def _known_query_kinds(cls, value: tuple[str, ...] | None) -> tuple[str, ...] | None:
        return None if value is None else _query_kinds(value)


class WriterThresholds(BaseModel):
    """
    The effective settings for writing one draft (src/services/writer/,
    docs/decisions/writing.md). Defaults come from `settings`, like
    PipelineThresholds; `resolve` merges a request's overrides the same way.

    A model of its own rather than more PipelineThresholds fields, for the
    reason a discovery round's `topicEmphasis` is not one either (see
    docs/decisions/thresholds.md): nothing here judges anything an
    analysis does. As PipelineThresholds fields they would change every
    analysis cache key and every evaluation run's config id, and /analyze
    would accept knobs that do nothing there.
    """

    model_config = {"frozen": True}

    # How many articles from other outlets on the same story, at most.
    related_max_sources: int = Field(
        default_factory=lambda: settings.WRITER_RELATED_MAX_SOURCES,
        ge=0,
        le=12,
    )

    # How similar a corpus article must be to the analysed one to count as
    # the same story. By default the corpus's own definition of
    # "related" - the bar an internal source clears as evidence.
    related_min_similarity: float = Field(
        default_factory=lambda: settings.RELATEDNESS_THRESHOLD,
        ge=0.0,
        le=1.0,
    )

    # A related article dated more than this many days before the analysed
    # one is background, not the same story. Later ones are follow-ups and
    # are kept.
    related_max_age_days: int = Field(
        default_factory=lambda: settings.WRITER_RELATED_MAX_AGE_DAYS,
        ge=1,
        le=3650,
    )

    related_excerpt_chars: int = Field(
        default_factory=lambda: settings.WRITER_RELATED_EXCERPT_CHARS,
        ge=200,
        le=8000,
    )

    analysed_excerpt_chars: int = Field(
        default_factory=lambda: settings.WRITER_ANALYSED_EXCERPT_CHARS,
        ge=500,
        le=20000,
    )

    evidence_max_sources: int = Field(
        default_factory=lambda: settings.WRITER_EVIDENCE_MAX_SOURCES,
        ge=0,
        le=20,
    )

    evidence_excerpt_chars: int = Field(
        default_factory=lambda: settings.WRITER_EVIDENCE_EXCERPT_CHARS,
        ge=100,
        le=4000,
    )

    max_output_tokens: int = Field(
        default_factory=lambda: settings.WRITER_MAX_OUTPUT_TOKENS,
        ge=256,
        le=16384,
    )

    prompt_max_chars: int = Field(
        default_factory=lambda: settings.WRITER_PROMPT_MAX_CHARS,
        ge=4000,
        le=400000,
    )

    @classmethod
    def resolve(
        cls,
        overrides: Optional["WriterThresholdOverrides"] = None,
    ) -> "WriterThresholds":

        if overrides is None:
            return cls()

        return cls(**overrides.model_dump(exclude_none=True))


class WriterThresholdOverrides(BaseModel):
    """
    A draft request's overrides: every field optional, names and bounds
    mirroring WriterThresholds (test_invariants.py holds the two together).
    """

    model_config = {"extra": "forbid"}

    related_max_sources: Optional[int] = Field(None, ge=0, le=12)
    related_min_similarity: Optional[float] = Field(None, ge=0.0, le=1.0)
    related_max_age_days: Optional[int] = Field(None, ge=1, le=3650)
    related_excerpt_chars: Optional[int] = Field(None, ge=200, le=8000)
    analysed_excerpt_chars: Optional[int] = Field(None, ge=500, le=20000)
    evidence_max_sources: Optional[int] = Field(None, ge=0, le=20)
    evidence_excerpt_chars: Optional[int] = Field(None, ge=100, le=4000)
    max_output_tokens: Optional[int] = Field(None, ge=256, le=16384)
    prompt_max_chars: Optional[int] = Field(None, ge=4000, le=400000)


class RewriteTargets(BaseModel):
    """
    "The metrics expected" of a draft: the lowest score, 0-100, each of
    the review's nine metrics may have before the rewrite stage counts it
    as below target (src/services/writer/rewriter.py,
    docs/decisions/writing.md, "Rewriting"). Higher is better on every
    metric, hallucinationIndex included, so every target is a floor.

    A pair of its own, apart from both PipelineThresholds and
    WriterThresholds, for the reason the writer's pair is apart from the
    pipeline's: these judge a review, which neither an analysis nor the
    writing of a draft does. As PipelineThresholds fields they would
    change every analysis cache key and evaluation config id; as
    WriterThresholds fields, `POST /drafts` would accept nine knobs that
    do nothing when a draft is created.

    Over the API the names are the review's own metric keys
    (`factConsistency`, not `fact_consistency`), so a target and the
    metric it is for are looked up with one key.

    Defaults are reasoned, not fitted - no review has been scored by a
    person to fit them against. Not from `settings`: the metrics have no
    environment of their own, and a request overrides any of them.

    - The two that are about truth are the strictest: one fault fails
      them. A citation to no source costs factConsistency 20 of its
      ceiling (draft_reviewer.DANGLING_CITATION_PENALTY), so one leaves
      it at 80, under 85. hallucinationIndex is capped at the share of
      factual sentences that cite a source, so 85 lets one uncited
      sentence pass among seven or more, and fails it among six or fewer.
    - grammar 80: errors are what a reader sees first, and the most
      common failure measured in Catalan drafts (writing.md, "The model").
    - title, subtitle, style 70: the review panel's own "good" tier, the
      colour /corrector and the draft review already draw at 70. A
      missing subtitle is capped at 20, so it always fails.
    - seo 60: the least strict of the model's metrics. It costs a
      reader nothing; an untrue sentence does.
    - readability 50: reading ease on Flesch's scale (Fernández-Huerta's
      for Spanish, and its stand-in for Catalan, map onto the same
      bands). 50-60 is "fairly difficult", under 50 "difficult" - prose
      for specialists, not a general reader.
    - coverageVerification 30: the positive-impact score, x100, at the
      bar the running newsroom admits articles at (0.3 in the author's
      .env, docs/experiments.md "admission"), not the code's 0.1, which
      admits almost anything. A draft should fit the mission at least as
      well as an article must to be checked at all.
    """

    model_config = ConfigDict(frozen=True, alias_generator=to_camel, populate_by_name=True)

    title: float = Field(default=70.0, ge=0.0, le=100.0)

    subtitle: float = Field(default=70.0, ge=0.0, le=100.0)

    grammar: float = Field(default=80.0, ge=0.0, le=100.0)

    fact_consistency: float = Field(default=85.0, ge=0.0, le=100.0)

    coverage_verification: float = Field(default=30.0, ge=0.0, le=100.0)

    seo: float = Field(default=60.0, ge=0.0, le=100.0)

    readability: float = Field(default=50.0, ge=0.0, le=100.0)

    hallucination_index: float = Field(default=85.0, ge=0.0, le=100.0)

    style: float = Field(default=70.0, ge=0.0, le=100.0)

    @classmethod
    def resolve(
        cls,
        overrides: Optional["RewriteTargetOverrides"] = None,
    ) -> "RewriteTargets":

        if overrides is None:
            return cls()

        return cls(**overrides.model_dump(exclude_none=True))

    def by_metric(self) -> dict[str, float]:
        """Each target under its review metric's key: {"factConsistency": 85.0, ...}."""

        return self.model_dump(by_alias=True)


class RewriteTargetOverrides(BaseModel):
    """
    A rewrite request's targets: every field optional, names and bounds
    mirroring RewriteTargets (test_invariants.py holds the two together),
    sent under the review's metric keys.
    """

    model_config = ConfigDict(extra="forbid", alias_generator=to_camel, populate_by_name=True)

    title: Optional[float] = Field(None, ge=0.0, le=100.0)
    subtitle: Optional[float] = Field(None, ge=0.0, le=100.0)
    grammar: Optional[float] = Field(None, ge=0.0, le=100.0)
    fact_consistency: Optional[float] = Field(None, ge=0.0, le=100.0)
    coverage_verification: Optional[float] = Field(None, ge=0.0, le=100.0)
    seo: Optional[float] = Field(None, ge=0.0, le=100.0)
    readability: Optional[float] = Field(None, ge=0.0, le=100.0)
    hallucination_index: Optional[float] = Field(None, ge=0.0, le=100.0)
    style: Optional[float] = Field(None, ge=0.0, le=100.0)
