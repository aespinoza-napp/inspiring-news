from unittest.mock import Mock

from src.config.thresholds import PipelineThresholds
from src.models.fact_checker.evidence import EvidenceOrigin, RejectedEvidence
from src.models.fact_checker.fact_check import FactCheck, Verdict
from src.models.fact_checker.pipeline_stage import PipelineStage
from src.services.claim_service import ClaimService

from tests.factories import create_evidence
from tests.fact_checker.fakes import FakeEntityExtractor

CLAIM = "NASA discovered water on Mars in 2024."


def make_check(**kwargs) -> FactCheck:

    defaults = dict(
        verdict=Verdict.TRUE,
        explanation="Confirmed by two sources.",
        confidence=0.82,
        claim=CLAIM,
        evidence=[create_evidence(url="https://a.example", relevance_score=0.9)],
        cited_evidence_indices=[0],
        evidence_count=1,
    )
    defaults.update(kwargs)

    return FactCheck(**defaults)


def make_service(check=None, entity_extractor=None):

    fact_checker = Mock()
    fact_checker.check_claim.return_value = check if check is not None else make_check()

    return ClaimService(
        fact_checker=fact_checker,
        entity_extractor=entity_extractor or FakeEntityExtractor({"organization": ["NASA"]}),
    )


# ----------------------------------------------------------------------
# Building the claim
# ----------------------------------------------------------------------


def test_entities_are_extracted_with_the_shared_extractor():

    extractor = FakeEntityExtractor({"organization": ["NASA"]})

    service = make_service(entity_extractor=extractor)

    result = service.verify(CLAIM)

    assert result["entities"] == {"organization": ["NASA"]}
    assert extractor.calls[0][0] == CLAIM


def test_the_entity_threshold_is_passed_through():

    extractor = FakeEntityExtractor({"organization": ["NASA"]})

    make_service(entity_extractor=extractor).verify(
        CLAIM,
        thresholds=PipelineThresholds(entity_threshold=0.9),
    )

    assert extractor.calls[0][1] == 0.9


def test_a_user_supplied_claim_is_never_scored_away():
    """
    Inside an article, claim confidence ranks sentences against each
    other to decide which are worth checking. A claim submitted directly
    has already been chosen by the user, so scoring it could only
    discard it - it goes in at 1.0.
    """

    service = make_service()

    service.verify("Barcelona is beautiful.")

    claim = service.fact_checker.check_claim.call_args[0][0]

    assert claim.confidence == 1.0
    assert claim.text == "Barcelona is beautiful."


def test_surrounding_whitespace_is_stripped():

    service = make_service()

    service.verify("   NASA discovered water.  \n")

    assert service.fact_checker.check_claim.call_args[0][0].text == (
        "NASA discovered water."
    )


# ----------------------------------------------------------------------
# Verification reuses the pipeline's own checker
# ----------------------------------------------------------------------


def test_verification_delegates_to_the_fact_checker():

    service = make_service()

    service.verify(CLAIM, thresholds=PipelineThresholds(max_evidence_per_claim=3))

    kwargs = service.fact_checker.check_claim.call_args.kwargs

    assert kwargs["thresholds"].max_evidence_per_claim == 3


def test_the_verdict_and_explanation_are_reported():

    result = make_service().verify(CLAIM)

    assert result["claim"] == CLAIM
    assert result["verdict"] == Verdict.TRUE
    assert result["confidence"] == 0.82
    assert result["explanation"] == "Confirmed by two sources."
    assert result["evidenceCount"] == 1


def test_evidence_is_flagged_as_cited_or_not():

    check = make_check(
        evidence=[
            create_evidence(url="https://cited.example"),
            create_evidence(url="https://ignored.example"),
        ],
        cited_evidence_indices=[0],
        evidence_count=2,
    )

    result = make_service(check=check).verify(CLAIM)

    assert [item["url"] for item in result["evidence"]] == [
        "https://cited.example",
        "https://ignored.example",
    ]
    assert [item["cited"] for item in result["evidence"]] == [True, False]


def test_rejected_sources_are_reported_for_transparency():

    check = make_check(
        rejected_sources=[
            RejectedEvidence(
                url="https://cut.example",
                title="Cut",
                origin=EvidenceOrigin.WEB,
                stage=PipelineStage.EVIDENCE_RANKING,
                reason="cut by final ranking cap",
                score=0.2,
            )
        ]
    )

    result = make_service(check=check).verify(CLAIM)

    assert result["rejectedSources"][0]["url"] == "https://cut.example"
    assert result["rejectedSources"][0]["stage"] == PipelineStage.EVIDENCE_RANKING


def test_an_unverifiable_claim_reports_the_forced_downgrade():
    """
    No evidence means UNVERIFIED regardless of what the LLM said - and
    the raw verdict is kept alongside so the downgrade is visible rather
    than silently rewritten.
    """

    check = make_check(
        verdict=Verdict.UNVERIFIED,
        confidence=0.0,
        explanation="No evidence could be retrieved for this claim.",
        evidence=[],
        cited_evidence_indices=[],
        evidence_count=0,
        reached_stage=PipelineStage.CONFIDENCE_RECALIBRATION,
        stage_note="No evidence could be retrieved for this claim.",
        raw_verdict=Verdict.TRUE,
        raw_confidence=0.95,
    )

    result = make_service(check=check).verify(CLAIM)

    assert result["verdict"] == Verdict.UNVERIFIED
    assert result["evidence"] == []
    assert result["reachedStage"] == PipelineStage.CONFIDENCE_RECALIBRATION
    assert result["rawVerdict"] == Verdict.TRUE
    assert result["rawConfidence"] == 0.95


def test_the_effective_thresholds_are_echoed_back():

    result = make_service().verify(
        CLAIM,
        thresholds=PipelineThresholds(max_evidence_per_claim=2),
    )

    assert result["thresholds"]["max_evidence_per_claim"] == 2


# ----------------------------------------------------------------------
# Phases
# ----------------------------------------------------------------------


def test_phases_are_reported_in_order():

    events = []

    make_service().verify(CLAIM, on_phase=lambda phase, data: events.append(phase))

    assert events == ["extracting_entities", "verifying", "done"]


def test_the_phase_callback_is_forwarded_to_the_fact_checker():
    """
    So a caller sees the retrieval/ranking/LLM phases too, not just the
    two this service emits itself.
    """

    service = make_service()

    service.verify(CLAIM, on_phase=lambda phase, data: None)

    assert service.fact_checker.check_claim.call_args.kwargs["on_phase"] is not None
