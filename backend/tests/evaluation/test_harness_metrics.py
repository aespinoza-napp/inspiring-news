"""
Every metric against a value worked out by hand. A wrong metric is a
wrong paper (roadmap, testing track, November).

The fixture: ten scored claims, gold -> predicted

     1 TRUE -> TRUE            6 FALSE -> TRUE
     2 TRUE -> TRUE            7 MISLEADING -> MISLEADING
     3 TRUE -> UNVERIFIED      8 MISLEADING -> FALSE
     4 TRUE -> PARTIALLY_TRUE  9 UNVERIFIED -> UNVERIFIED
     5 FALSE -> FALSE         10 PARTIALLY_TRUE -> UNVERIFIED

gold      TRUE 4, PARTIALLY_TRUE 1, MISLEADING 2, FALSE 2, UNVERIFIED 1
predicted TRUE 3, PARTIALLY_TRUE 1, MISLEADING 1, FALSE 2, UNVERIFIED 3
right     TRUE 2, MISLEADING 1, FALSE 1, UNVERIFIED 1      (5 of 10)
"""

import pytest

from src.evaluation import metrics
from src.evaluation.metrics import (
    ERROR,
    LLM_UNREACHABLE,
    SCORED,
    SEARCH_UNAVAILABLE,
    bootstrap,
    classification,
    discordant,
    paired_bootstrap,
)

from tests.evaluation.support import custom_row, make_record, source, xfact_row

PAIRS = [
    ("TRUE", "TRUE"),
    ("TRUE", "TRUE"),
    ("TRUE", "UNVERIFIED"),
    ("TRUE", "PARTIALLY_TRUE"),
    ("FALSE", "FALSE"),
    ("FALSE", "TRUE"),
    ("MISLEADING", "MISLEADING"),
    ("MISLEADING", "FALSE"),
    ("UNVERIFIED", "UNVERIFIED"),
    ("PARTIALLY_TRUE", "UNVERIFIED"),
]


def fixture_records() -> list[dict]:
    """The ten pairs above, as records written by record.py."""

    return [
        make_record(xfact_row(f"Claim {n}.", label=gold), predicted)
        for n, (gold, predicted) in enumerate(PAIRS, start=1)
    ]


def test_accuracy_is_the_share_right():

    assert classification(PAIRS)["accuracy"] == 0.5


def test_per_class_precision_recall_f1_and_support():

    per_class = classification(PAIRS)["perClass"]

    assert per_class["TRUE"] == {
        "precision": pytest.approx(2 / 3), "recall": 0.5,
        # 2PR/(P+R) = 2*2 / (4 gold + 3 predicted)
        "f1": pytest.approx(4 / 7), "support": 4, "predicted": 3,
    }
    assert per_class["PARTIALLY_TRUE"] == {
        "precision": 0.0, "recall": 0.0, "f1": 0.0, "support": 1, "predicted": 1,
    }
    assert per_class["MISLEADING"] == {
        "precision": 1.0, "recall": 0.5, "f1": pytest.approx(2 / 3), "support": 2, "predicted": 1,
    }
    assert per_class["FALSE"] == {
        "precision": 0.5, "recall": 0.5, "f1": 0.5, "support": 2, "predicted": 2,
    }
    assert per_class["UNVERIFIED"] == {
        "precision": pytest.approx(1 / 3), "recall": 1.0, "f1": 0.5, "support": 1, "predicted": 3,
    }


def test_macro_f1_averages_the_gold_classes():

    # (4/7 + 0 + 2/3 + 1/2 + 1/2) / 5 = 47/105
    assert classification(PAIRS)["macroF1"] == pytest.approx(47 / 105)


def test_a_class_without_gold_support_is_shown_but_not_averaged():
    """The custom set has no FALSE yet; predicting it must not cost a zero."""

    pairs = [("TRUE", "TRUE"), ("TRUE", "FALSE"), ("UNVERIFIED", "UNVERIFIED")]

    result = classification(pairs)

    assert result["goldClasses"] == ["TRUE", "UNVERIFIED"]

    assert result["perClass"]["FALSE"] == {
        "precision": 0.0, "recall": None, "f1": None, "support": 0, "predicted": 1,
    }

    # TRUE: 2*1/(2+1) = 2/3; UNVERIFIED: 2*1/(1+1) = 1
    assert result["macroF1"] == pytest.approx((2 / 3 + 1) / 2)


def test_the_confusion_matrix_is_gold_rows_by_predicted_columns():

    matrix = classification(PAIRS)["confusion"]

    assert matrix["TRUE"] == {
        "TRUE": 2, "PARTIALLY_TRUE": 1, "MISLEADING": 0, "FALSE": 0, "UNVERIFIED": 1,
    }
    assert matrix["FALSE"]["TRUE"] == 1
    assert matrix["MISLEADING"]["FALSE"] == 1
    assert matrix["PARTIALLY_TRUE"]["UNVERIFIED"] == 1
    assert sum(sum(row.values()) for row in matrix.values()) == 10


def test_coverage_and_selective_accuracy():

    result = classification(PAIRS)

    # 7 of 10 are not UNVERIFIED; of those 7, 4 are right (5 minus the
    # UNVERIFIED that was right).
    assert result["coverage"] == 0.7
    assert result["selectiveAccuracy"] == pytest.approx(4 / 7)


def test_cohens_kappa_against_gold():

    # chance = (4*3 + 1*1 + 2*1 + 2*2 + 1*3) / 100 = 0.22
    # kappa = (0.5 - 0.22) / (1 - 0.22)
    assert classification(PAIRS)["kappa"] == pytest.approx(0.28 / 0.78)


def test_kappa_is_undefined_when_both_sides_use_one_label():

    assert classification([("TRUE", "TRUE")] * 3)["kappa"] is None


def test_no_definitive_verdict_has_no_selective_accuracy():

    result = classification([("TRUE", "UNVERIFIED"), ("FALSE", "UNVERIFIED")])

    assert result["coverage"] == 0
    assert result["selectiveAccuracy"] is None


def test_an_empty_set_has_no_metrics():

    result = classification([])

    assert result["n"] == 0
    assert result["accuracy"] is None
    assert result["macroF1"] is None


# ----------------------------------------------------------------------
# Outcomes and flags
# ----------------------------------------------------------------------


def test_each_claim_gets_exactly_one_outcome_in_order():

    row = xfact_row("A claim.")

    assert metrics.outcome(make_record(row, error=RuntimeError("boom"))) == ERROR

    assert metrics.outcome(make_record(row, search_unavailable=True)) == SEARCH_UNAVAILABLE

    # Search first: both failed, and the web was never asked.
    assert metrics.outcome(
        make_record(row, search_unavailable=True, llm_unreachable=True)
    ) == SEARCH_UNAVAILABLE

    assert metrics.outcome(make_record(row, llm_unreachable=True)) == LLM_UNREACHABLE

    assert metrics.outcome(make_record(row, "TRUE")) == SCORED


def test_a_cited_source_newer_than_the_claim_is_a_temporal_leak():

    row = custom_row("fact001", "Una afirmación.", claimDate="2026-09-01")

    newer = make_record(row, "TRUE", evidence=[source("https://a.org/x", published="2026-09-15T08:00:00")], cited=[0])
    older = make_record(row, "TRUE", evidence=[source("https://a.org/x", published="2026-08-01T08:00:00")], cited=[0])
    same_day = make_record(row, "TRUE", evidence=[source("https://a.org/x", published="2026-09-01T23:00:00")], cited=[0])
    undated = make_record(row, "TRUE", evidence=[source("https://a.org/x")], cited=[0])
    uncited = make_record(row, "TRUE", evidence=[source("https://a.org/x", published="2026-09-15T08:00:00")], cited=[])

    assert metrics.temporal_leak(newer) is True
    assert metrics.temporal_leak(older) is False
    assert metrics.temporal_leak(same_day) is False
    assert metrics.temporal_leak(undated) is None

    # Ranked but uncited newer sources are counted, not flagged.
    assert metrics.temporal_leak(uncited) is False
    assert metrics.newer_uncited(uncited) == 1


def test_a_claim_without_a_date_cannot_be_checked_for_a_temporal_leak():
    """Every one of the 40 chequeado pilot rows."""

    record = make_record(
        xfact_row("Una afirmación.", site="chequeado.com"), "TRUE",
        evidence=[source("https://a.org/x", published="2026-09-15T08:00:00")], cited=[0],
    )

    assert metrics.temporal_leak(record) is None


def test_a_ranked_source_on_the_fact_checkers_own_site_is_a_verdict_leak():

    row = xfact_row("Una afirmación.", language="es", site="chequeado.com")

    leaked = make_record(row, "FALSE", evidence=[source("https://www.chequeado.com/ultimas-noticias/x/")])
    subdomain = make_record(row, "FALSE", evidence=[source("https://blog.chequeado.com/x")])
    clean = make_record(row, "FALSE", evidence=[source("https://lanacion.com.ar/x")])

    assert metrics.verdict_leak(leaked) is True
    assert metrics.verdict_leak(subdomain) is True
    assert metrics.verdict_leak(clean) is False

    # The custom set's site is the article's publisher, not a fact-checker.
    custom = make_record(custom_row("fact001", "Uno."), "TRUE", evidence=[source("https://lacarabuenadelmundo.com/x")])

    assert metrics.verdict_leak(custom) is None


# ----------------------------------------------------------------------
# Bootstrap
# ----------------------------------------------------------------------


def test_the_bootstrap_is_deterministic_under_a_fixed_seed():

    first = bootstrap(PAIRS, seed=7, resamples=2000)
    second = bootstrap(PAIRS, seed=7, resamples=2000)

    assert first == second

    assert bootstrap(PAIRS, seed=8, resamples=2000) != first


def test_the_interval_brackets_the_estimate_and_stays_in_range():

    ci = bootstrap(PAIRS, seed=7, resamples=2000)

    assert 0 <= ci["accuracy"]["low"] <= 0.5 <= ci["accuracy"]["high"] <= 1
    assert ci["accuracy"]["low"] < ci["accuracy"]["high"]


def test_a_perfect_run_has_a_degenerate_interval():

    ci = bootstrap([("TRUE", "TRUE"), ("FALSE", "FALSE")] * 5, seed=1, resamples=500)

    assert (ci["accuracy"]["low"], ci["accuracy"]["high"]) == (1.0, 1.0)


def test_undefined_resamples_are_skipped_and_counted():

    # One definitive verdict in eight: some resamples draw none of it.
    pairs = [("TRUE", "TRUE")] + [("FALSE", "UNVERIFIED")] * 7

    ci = bootstrap(pairs, seed=3, resamples=1000)

    assert ci["selectiveAccuracy"]["undefinedResamples"] > 0
    assert ci["accuracy"]["undefinedResamples"] == 0


def test_the_paired_bootstrap_of_identical_runs_is_exactly_zero():

    result = paired_bootstrap(PAIRS, PAIRS, seed=7, resamples=1000)

    for name, value in result.items():
        if value["difference"] is None:
            continue
        assert value["difference"] == 0, name
        assert (value["low"], value["high"]) == (0, 0), name


def test_the_paired_bootstrap_sees_a_uniformly_better_model():

    worse = [(gold, "UNVERIFIED") for gold, _ in PAIRS]

    result = paired_bootstrap(worse, PAIRS, seed=7, resamples=1000)

    # B - A: 0.5 - 0.1 (only claim 9 was right as UNVERIFIED)
    assert result["accuracy"]["difference"] == pytest.approx(0.4)
    assert result["accuracy"]["low"] > 0

    assert discordant(worse, PAIRS) == {"onlyA": 0, "onlyB": 4}


def test_a_paired_comparison_refuses_claims_that_are_not_the_same():

    with pytest.raises(ValueError):
        paired_bootstrap(PAIRS, PAIRS[:-1])

    with pytest.raises(ValueError):
        paired_bootstrap([("TRUE", "TRUE")], [("FALSE", "TRUE")])


def test_records_written_by_record_py_give_the_same_metrics():
    """The report reads `label` and `verdict` off records; same numbers."""

    records = fixture_records()

    pairs = [(record["label"], record["verdict"]) for record in records]

    assert pairs == PAIRS
