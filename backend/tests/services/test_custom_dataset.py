import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config.topics import TOPICS
from src.models.evaluation.custom_fact import (
    XFACT_FIELDS,
    CustomFactInput,
    CustomFactReview,
)
from src.models.fact_checker.fact_check import Verdict
from src.repositories.custom_fact_repository import CustomFactRepository
from src.services.custom_dataset import (
    TOPIC_GROUPS,
    CustomDatasetService,
    agreement,
    review_sample,
    summarise,
)

PILOT = Path(__file__).resolve().parents[2] / "data" / "evaluation" / "xfact_en_es_pilot.jsonl"


def fact_input(**overrides) -> CustomFactInput:

    data = {
        "claim": "The reserve's otter population doubled between 2015 and 2024.",
        "language": "en",
        "articleUrl": "https://www.positive.news/environment/otters/",
        "claimDate": "2025-03-02",
        "label": "TRUE",
        "referenceEvidenceLinks": ["https://example.org/census-2024.pdf"],
        "topic": "nature",
        "claimType": "numerical",
        "sourceTier": "primary",
    }
    data.update(overrides)

    return CustomFactInput(**data)


@pytest.fixture
def service(tmp_path):

    return CustomDatasetService(CustomFactRepository(tmp_path / "custom.jsonl"))


# ----------------------------------------------------------------------
# Same shape as x-fact
# ----------------------------------------------------------------------


def test_a_stored_fact_starts_with_xfacts_keys_in_xfacts_order(service, tmp_path):

    service.create(fact_input())

    row = json.loads((tmp_path / "custom.jsonl").read_text(encoding="utf-8"))

    assert tuple(row)[: len(XFACT_FIELDS)] == XFACT_FIELDS


def test_the_xfact_keys_carry_the_same_types_as_the_committed_pilot(service, tmp_path):
    """Whatever loads the x-fact set must load this one unchanged."""

    service.create(fact_input())

    ours = json.loads((tmp_path / "custom.jsonl").read_text(encoding="utf-8"))
    theirs = json.loads(PILOT.read_text(encoding="utf-8").splitlines()[0])

    assert tuple(theirs) == XFACT_FIELDS

    for key in XFACT_FIELDS:
        if theirs[key] is None or ours[key] is None:
            continue
        assert type(ours[key]) is type(theirs[key]), key

    assert ours["label"] in {v.value for v in Verdict}
    assert ours["labelRaw"] == "supported"
    assert ours["split"] == "test"


def test_spanish_is_written_unescaped(service, tmp_path):

    service.create(fact_input(claim="La población de nutrias se duplicó.", language="es"))

    assert "población" in (tmp_path / "custom.jsonl").read_text(encoding="utf-8")


# ----------------------------------------------------------------------
# The guide's rules the form enforces
# ----------------------------------------------------------------------


def test_every_topic_is_in_exactly_one_balance_group():

    grouped = [t for topics in TOPIC_GROUPS.values() for t in topics]

    assert sorted(grouped) == sorted(TOPICS)


def test_a_verdict_other_than_unverified_needs_a_link():

    with pytest.raises(ValidationError, match="evidence link"):
        fact_input(referenceEvidenceLinks=[])

    assert fact_input(label="UNVERIFIED", referenceEvidenceLinks=[]).label == Verdict.UNVERIFIED


def test_only_the_organisations_own_source_is_not_enough_evidence():

    with pytest.raises(ValidationError, match="UNVERIFIED"):
        fact_input(onlyOwnSource=True, annotatorNote="NGO press release")

    with pytest.raises(ValidationError, match="annotator note"):
        fact_input(onlyOwnSource=True, label="UNVERIFIED")

    fact = fact_input(onlyOwnSource=True, label="UNVERIFIED", annotatorNote="Only the NGO's release")
    assert fact.onlyOwnSource


def test_evidence_newer_than_the_article_is_rejected():

    with pytest.raises(ValidationError, match="newer than the article"):
        fact_input(evidenceDate="2025-04-01")

    assert fact_input(evidenceDate="2025-03-02").evidenceDate == date(2025, 3, 2)


def test_an_unknown_topic_and_a_non_http_link_are_rejected():

    with pytest.raises(ValidationError, match="Unknown topic"):
        fact_input(topic="politics")

    with pytest.raises(ValidationError, match="http"):
        fact_input(referenceEvidenceLinks=["javascript:alert(1)"])


def test_the_site_defaults_to_the_articles_domain():

    assert fact_input().site == "positive.news"

    with pytest.raises(ValidationError, match="site"):
        fact_input(articleUrl=None)


# ----------------------------------------------------------------------
# Repository
# ----------------------------------------------------------------------


def test_update_and_delete_rewrite_the_file(service):

    fact = service.create(fact_input())
    other = service.create(fact_input(claim="Another claim."))

    updated = service.update(fact.id, fact_input(label="FALSE"))

    assert updated.label == Verdict.FALSE
    assert updated.createdAt == fact.createdAt
    assert [f.label for f in service.repository.list()] == [Verdict.FALSE, Verdict.TRUE]

    assert service.delete(other.id)
    assert [f.id for f in service.repository.list()] == [fact.id]
    assert not service.delete("missing")
    assert service.update("missing", fact_input()) is None


# ----------------------------------------------------------------------
# Balance, review sample, agreement
# ----------------------------------------------------------------------


def test_the_balance_matrix_counts_verdict_by_topic_group(service):

    service.create(fact_input())
    service.create(fact_input(topic="climate", label="FALSE"))
    service.create(fact_input(topic="medicine", language="es"))

    summary = summarise(service.repository.list())

    assert summary["total"] == 3
    assert summary["matrix"]["TRUE"]["environment"] == 1
    assert summary["matrix"]["FALSE"]["environment"] == 1
    assert summary["matrix"]["TRUE"]["health"] == 1
    assert summary["byLanguage"] == {"en": 2, "es": 1}


def test_the_review_sample_is_a_stable_fifth(service):

    for i in range(11):
        service.create(fact_input(claim=f"Claim {i}"))

    facts = service.repository.list()
    sample = review_sample(facts)

    assert len(sample) == 3  # ceil(11 * 0.2)
    assert [f.id for f in review_sample(list(reversed(facts)))] == [f.id for f in sample]


def test_a_reviewed_fact_stays_in_the_sample(service):

    for i in range(10):
        service.create(fact_input(claim=f"Claim {i}"))

    outside = next(
        f for f in service.repository.list()
        if f.id not in {s.id for s in review_sample(service.repository.list())}
    )
    service.review(outside.id, CustomFactReview(label="TRUE"))

    assert outside.id in {f.id for f in review_sample(service.repository.list())}


def test_the_review_queue_is_blind(service):

    fact = service.create(fact_input(annotatorNote="Checked the census PDF"))

    item = service.review_queue()["sample"][0]

    assert item["id"] == fact.id
    assert "label" not in item and "labelRaw" not in item and "annotatorNote" not in item


def test_agreement_is_measured_on_the_first_label_even_after_a_correction(service):

    fact = service.create(fact_input())

    service.review(fact.id, CustomFactReview(label="PARTIALLY_TRUE"))
    # The disagreement is resolved by correcting the label ...
    service.update(fact.id, fact_input(label="PARTIALLY_TRUE"))

    # ... which must not turn it into an agreement after the fact.
    result = agreement(service.repository.list())

    assert result["reviewed"] == 1
    assert result["observed"] == 0
    assert result["disagreements"][0]["firstLabel"] == "TRUE"


def test_cohens_kappa_discounts_chance_agreement(service):

    # Three of four pairs agree: observed 0.75.
    labels = [("TRUE", "TRUE"), ("TRUE", "TRUE"), ("FALSE", "FALSE"), ("FALSE", "TRUE")]

    for i, (first, second) in enumerate(labels):
        fact = service.create(fact_input(claim=f"Claim {i}", label=first))
        service.review(fact.id, CustomFactReview(label=second))

    result = agreement(service.repository.list())

    # first: TRUE 2, FALSE 2; second: TRUE 3, FALSE 1.
    # expected = (2*3 + 2*1) / 16 = 0.5; kappa = (0.75 - 0.5) / 0.5 = 0.5
    assert result["observed"] == 0.75
    assert result["kappa"] == 0.5


def test_kappa_is_undefined_when_every_label_is_the_same(service):

    fact = service.create(fact_input())
    service.review(fact.id, CustomFactReview(label="TRUE"))

    result = agreement(service.repository.list())

    assert result["observed"] == 1
    assert result["kappa"] is None
