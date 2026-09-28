"""
What the confidence weights do, pinned.

test_confidence_scorer.py covers the rules - no evidence, no citations,
a contradicting source, a single outlet. Nothing covered the arithmetic
underneath: every numeric assertion there was a loose bound (`> 0.6`),
and it ran on whatever weights `.env` held when the scorer was imported
(tests/frozen_settings.py). So a change to CONFIDENCE_*_WEIGHT, or to the
0.5 / 0.3 / 0.2 split inside the evidence term, passed the suite
unnoticed.

These are not measured against labelled data - none exists yet (see
docs/roadmap.md, "Tune RANKING_*, CONFIDENCE_*"). They pin the behaviour
as declared, so that when the weights are tuned the change is a failing
test someone updates on purpose, with the new numbers in the diff.
"""

import itertools

import pytest
from pydantic import ValidationError

from src.config.settings import Settings
from src.config.thresholds import PipelineThresholds
from src.models.fact_checker.fact_check import Verdict
from src.services.fact_checker.verification.confidence_scorer import ConfidenceScorer
from src.services.fact_checker.verification.llm_verification import LLMVerificationResult

from tests.factories import create_claim, create_evidence

# Explicit, so the golden values below do not move with a default.
THRESHOLDS = PipelineThresholds(
    max_evidence_per_claim=5,
    min_independent_domains=2,
    min_evidence_for_verdict=1,
)


def evidence(*relevances: float) -> list:
    """One item per relevance, each from its own domain."""

    return [
        create_evidence(
            url=f"https://source{index}.example/a",
            domain=f"source{index}.example",
            relevance_score=relevance,
        )
        for index, relevance in enumerate(relevances)
    ]


def score(
    items: list,
    llm_confidence: float,
    cited: list[int],
    verdict: Verdict = Verdict.FALSE,
) -> float:
    """
    FALSE by default: it is definitive, so it exercises the weights, and
    neither of TRUE's own adjustments (contradiction, single outlet)
    applies to it.
    """

    result = ConfidenceScorer().score(
        create_claim(),
        items,
        LLMVerificationResult(
            verdict=verdict,
            confidence=llm_confidence,
            explanation="",
            cited_evidence=cited,
        ),
        THRESHOLDS,
    )

    return result.confidence


# ----------------------------------------------------------------------
# The declared weights
# ----------------------------------------------------------------------


def test_the_suite_scores_with_the_declared_weights():

    fields = Settings.model_fields

    assert ConfidenceScorer.LLM_WEIGHT == fields["CONFIDENCE_LLM_WEIGHT"].default == 0.7
    assert ConfidenceScorer.EVIDENCE_WEIGHT == fields["CONFIDENCE_EVIDENCE_WEIGHT"].default == 0.3


@pytest.mark.parametrize("overrides", [
    {"CONFIDENCE_LLM_WEIGHT": 0.8},
    {"PERTINENCE_LEXICAL_WEIGHT": 0.6},
    # The committed .env-example's ranking weights until 2026-09-28:
    # 0.60 + 0.25 + 0.15, written before the lexical 0.20 existed.
    {"RANKING_SEMANTIC_WEIGHT": 0.60, "RANKING_RECENCY_WEIGHT": 0.25},
    {"CONFIDENCE_LLM_WEIGHT": 1.2, "CONFIDENCE_EVIDENCE_WEIGHT": -0.2},
])
def test_settings_refuse_a_weight_group_that_does_not_sum_to_one(overrides):

    with pytest.raises(ValidationError, match="sum to 1.0"):
        Settings(_env_file=None, NEO4J_PASSWORD="unused", **overrides)


def test_a_group_changed_together_is_accepted():

    tuned = Settings(
        _env_file=None,
        NEO4J_PASSWORD="unused",
        CONFIDENCE_LLM_WEIGHT=0.6,
        CONFIDENCE_EVIDENCE_WEIGHT=0.4,
    )

    assert tuned.CONFIDENCE_LLM_WEIGHT == 0.6


# ----------------------------------------------------------------------
# Golden values: confidence = 0.7 * llm + 0.3 * evidence_quality, where
# evidence_quality = 0.5 * mean relevance + 0.3 * cited share
#                  + 0.2 * min(count / max_evidence, 1)
# ----------------------------------------------------------------------


@pytest.mark.parametrize("relevances, llm_confidence, cited, expected", [
    # quality 0.425 + 0.3 + 0.08 = 0.805 -> 0.63 + 0.2415
    ((0.9, 0.8), 0.9, [0, 1], 0.8715),
    # quality 0.2 + 0.3 + 0.04 = 0.54 -> 0.35 + 0.162
    ((0.4,), 0.5, [0], 0.512),
    # quality 0.25 + 0.15 + 0.08 = 0.48 -> 0.56 + 0.144
    ((0.6, 0.4), 0.8, [0], 0.704),
    # Everything at its maximum reaches exactly 1.0.
    ((1.0,) * 5, 1.0, [0, 1, 2, 3, 4], 1.0),
    # Perfect evidence, a model with no confidence: the evidence term alone.
    ((1.0,) * 5, 0.0, [0, 1, 2, 3, 4], 0.3),
])
def test_confidence_golden_values(relevances, llm_confidence, cited, expected):

    assert score(evidence(*relevances), llm_confidence, cited) == pytest.approx(expected)


# ----------------------------------------------------------------------
# Properties that should survive any retuning of the weights
# ----------------------------------------------------------------------


def test_the_model_outweighs_the_evidence():
    """
    The evidence term measures how good the sources look, not whether
    they back the verdict; only the model read them. So evidence alone
    must not be able to carry a claim the model is unsure of past one
    the model is sure of with weak sources.
    """

    unsure_with_perfect_sources = score(evidence(*(1.0,) * 5), 0.3, [0, 1, 2, 3, 4])
    sure_with_weak_sources = score(evidence(0.1), 0.9, [0])

    assert sure_with_weak_sources > unsure_with_perfect_sources


def test_padding_with_irrelevant_uncited_evidence_does_not_raise_confidence():
    """
    The quantity factor rewards more evidence. It must not reward a
    retrieval that pads the list with sources nobody cited.
    """

    focused = score(evidence(0.9, 0.8), 0.9, [0, 1])
    padded = score(evidence(0.9, 0.8, 0.0, 0.0, 0.0), 0.9, [0, 1])

    assert padded < focused


@pytest.mark.parametrize("field", ["llm", "relevance", "cited"])
def test_confidence_rises_with_each_input(field):

    low = {"llm": 0.4, "relevance": 0.4, "cited": [0]}
    high = dict(low, **{field: {"llm": 0.8, "relevance": 0.8, "cited": [0, 1]}[field]})

    def run(inputs):
        return score(evidence(inputs["relevance"], inputs["relevance"]), inputs["llm"], inputs["cited"])

    assert run(high) > run(low)


def test_confidence_stays_within_zero_and_one():

    for llm_confidence, relevance, count in itertools.product(
        (0.0, 0.5, 1.0), (0.0, 0.5, 1.0), (1, 3, 8),
    ):
        value = score(evidence(*(relevance,) * count), llm_confidence, list(range(count)))

        assert 0.0 <= value <= 1.0


def test_the_caps_hold_at_maximum_inputs():
    """
    The caps are rules, not weights: no amount of model confidence or
    evidence quality gets an uncited verdict past 0.4, or a TRUE resting
    on one outlet past 0.6.
    """

    perfect = evidence(*(1.0,) * 5)

    assert score(perfect, 1.0, [], verdict=Verdict.FALSE) <= 0.4

    one_outlet = [
        create_evidence(url=f"https://wire.example/{index}", domain="wire.example", relevance_score=1.0)
        for index in range(5)
    ]

    assert score(one_outlet, 1.0, [0, 1, 2, 3, 4], verdict=Verdict.TRUE) <= 0.6
