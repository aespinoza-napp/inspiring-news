import pytest
from pydantic import ValidationError

from src.config.settings import settings
from src.config.thresholds import PipelineThresholds, ThresholdOverrides


# ----------------------------------------------------------------------
# Defaults come from the environment
# ----------------------------------------------------------------------


def test_defaults_come_from_settings():

    thresholds = PipelineThresholds()

    assert thresholds.positive_impact_min_score == settings.POSITIVE_IMPACT_MIN_SCORE
    assert thresholds.topic_classifier_threshold == settings.TOPIC_CLASSIFIER_THRESHOLD
    assert thresholds.topic_min_confidence == settings.TOPIC_MIN_CONFIDENCE
    assert thresholds.entity_threshold == settings.ENTITY_THRESHOLD
    assert thresholds.claim_min_confidence == settings.CLAIM_MIN_CONFIDENCE
    assert thresholds.min_body_length == settings.MIN_BODY_LENGTH
    assert thresholds.duplicate_threshold == settings.DUPLICATE_THRESHOLD
    assert thresholds.relatedness_threshold == settings.RELATEDNESS_THRESHOLD
    assert thresholds.max_claims_per_article == settings.MAX_CLAIMS_PER_ARTICLE
    assert thresholds.claim_dedup_threshold == settings.CLAIM_DEDUP_THRESHOLD
    assert thresholds.max_evidence_per_claim == settings.MAX_EVIDENCE_PER_CLAIM
    assert thresholds.min_evidence_for_verdict == settings.MIN_EVIDENCE_FOR_VERDICT


def test_defaults_are_read_per_instance_not_frozen_at_import(monkeypatch):
    """
    The whole point of this module. Thresholds used to be class
    attributes (`MIN_SCORE = settings.MIN_SCORE`) evaluated once when the
    module was first imported, so changing the setting afterwards - or
    passing an override - had no effect anywhere.
    """

    monkeypatch.setattr(settings, "POSITIVE_IMPACT_MIN_SCORE", 0.77)

    assert PipelineThresholds().positive_impact_min_score == 0.77


# ----------------------------------------------------------------------
# Resolution: caller wins, environment fills the gaps
# ----------------------------------------------------------------------


def test_resolve_without_overrides_is_the_defaults():

    assert PipelineThresholds.resolve(None) == PipelineThresholds()


def test_resolve_with_an_empty_override_object_is_the_defaults():

    assert PipelineThresholds.resolve(ThresholdOverrides()) == PipelineThresholds()


def test_an_override_wins_and_the_rest_fall_back_to_defaults():

    resolved = PipelineThresholds.resolve(
        ThresholdOverrides(positive_impact_min_score=0.85)
    )

    assert resolved.positive_impact_min_score == 0.85

    # Everything else is untouched.
    assert resolved.topic_min_confidence == settings.TOPIC_MIN_CONFIDENCE
    assert resolved.max_claims_per_article == settings.MAX_CLAIMS_PER_ARTICLE


def test_several_overrides_apply_together():

    resolved = PipelineThresholds.resolve(
        ThresholdOverrides(
            topic_classifier_threshold=0.10,
            max_claims_per_article=1,
        )
    )

    assert resolved.topic_classifier_threshold == 0.10
    assert resolved.max_claims_per_article == 1


def test_an_explicit_none_is_not_an_override():
    """
    Sending `{"positive_impact_min_score": null}` means "I did not set
    this", not "set it to None" - otherwise a client serialising its
    whole form would wipe every default it left blank.
    """

    resolved = PipelineThresholds.resolve(
        ThresholdOverrides(positive_impact_min_score=None)
    )

    assert resolved.positive_impact_min_score == settings.POSITIVE_IMPACT_MIN_SCORE


def test_an_override_equal_to_the_default_is_still_valid():

    resolved = PipelineThresholds.resolve(
        ThresholdOverrides(
            positive_impact_min_score=settings.POSITIVE_IMPACT_MIN_SCORE
        )
    )

    assert resolved == PipelineThresholds()


# ----------------------------------------------------------------------
# What counts as "tuned"
# ----------------------------------------------------------------------


def test_a_default_run_reports_no_overrides():

    assert PipelineThresholds().overridden_from_defaults() == {}


def test_only_the_changed_fields_are_reported():

    resolved = PipelineThresholds.resolve(
        ThresholdOverrides(positive_impact_min_score=0.85, max_claims_per_article=2)
    )

    assert resolved.overridden_from_defaults() == {
        "positive_impact_min_score": 0.85,
        "max_claims_per_article": 2,
    }


def test_a_value_that_merely_restates_the_default_is_not_an_override():

    resolved = PipelineThresholds.resolve(
        ThresholdOverrides(max_claims_per_article=settings.MAX_CLAIMS_PER_ARTICLE)
    )

    assert resolved.overridden_from_defaults() == {}


# ----------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "field, value",
    [
        ("positive_impact_min_score", 1.5),
        ("positive_impact_min_score", -0.1),
        ("topic_classifier_threshold", 2.0),
        ("max_claims_per_article", 0),
        ("max_evidence_per_claim", 0),
        ("min_body_length", -1),
        ("min_evidence_for_verdict", -1),
    ],
)
def test_out_of_range_overrides_are_rejected(field, value):
    """
    Rejected at the edge, so a nonsensical value becomes a 422 on the
    request instead of a pipeline that silently admits everything (or
    nothing).
    """

    with pytest.raises(ValidationError):
        ThresholdOverrides(**{field: value})


def test_an_unknown_threshold_name_is_rejected():
    """
    `extra="forbid"`: a typo'd knob must fail loudly rather than be
    accepted and quietly ignored, leaving the caller to believe a
    threshold was applied when it never was.
    """

    with pytest.raises(ValidationError):
        ThresholdOverrides(positive_impact_treshold=0.5)


def test_pipeline_thresholds_rejects_out_of_range_values_too():

    with pytest.raises(ValidationError):
        PipelineThresholds(positive_impact_min_score=1.5)


def test_pipeline_thresholds_are_immutable():
    """
    One resolved set is shared across every stage of a run. If a stage
    could mutate it, later stages would silently see different values
    than earlier ones.
    """

    thresholds = PipelineThresholds()

    with pytest.raises(ValidationError):
        thresholds.positive_impact_min_score = 0.9


# ----------------------------------------------------------------------
# The two models must not drift apart
# ----------------------------------------------------------------------


def test_overrides_and_thresholds_expose_exactly_the_same_fields():
    """
    ThresholdOverrides is PipelineThresholds with every field made
    optional. Adding a knob to one and forgetting the other would make
    it silently un-overridable (or un-resolvable), so pin them together.
    """

    assert set(ThresholdOverrides.model_fields) == set(
        PipelineThresholds.model_fields
    )


def test_every_threshold_is_actually_overridable_end_to_end():
    """
    Walks every field, sets it to a legal value that differs from its
    default, and checks the resolved set carries it. Catches a field
    that exists on both models but is missing from `resolve`'s merge.
    """

    defaults = PipelineThresholds()

    for name, field in PipelineThresholds.model_fields.items():

        current = getattr(defaults, name)

        # A legal, different value: ints step up, floats move toward the
        # middle of [0, 1] without leaving it.
        if isinstance(current, int) and not isinstance(current, bool):
            candidate = current + 1
        else:
            candidate = round(current / 2, 4) if current > 0.02 else 0.5

        assert candidate != current, name

        resolved = PipelineThresholds.resolve(
            ThresholdOverrides(**{name: candidate})
        )

        assert getattr(resolved, name) == candidate, name
        assert resolved.overridden_from_defaults() == {name: candidate}, name
