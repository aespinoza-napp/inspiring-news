"""
A fixture run, reported: metrics.json, report.md and the manifest copy,
the paired comparison, and the models table. No live service; small
resample counts, since determinism is tested in test_harness_metrics.py.
"""

import json

import pytest

from src.evaluation import cli
from src.evaluation.report import load_run, models_table, write_report
from src.evaluation.usage import LLMCall, summarise

from tests.evaluation.support import (
    custom_row,
    make_record,
    source,
    write_run,
    xfact_row,
)
from tests.evaluation.test_harness_metrics import PAIRS, fixture_records

RESAMPLES = 300


def usage(prompt=1000, completion=100, latency=4.0):

    return summarise([LLMCall(latency=latency, ok=True, prompt_tokens=prompt, completion_tokens=completion)])


def fixture_run(directory, **kwargs):
    """The ten hand-computed claims, one leak, and one of each set-apart outcome."""

    records = fixture_records()

    leaked = make_record(
        xfact_row("Una afirmación chequeada.", language="es", site="chequeado.com", label="FALSE"),
        "FALSE",
        evidence=[source("https://chequeado.com/ultimas-noticias/x/")],
        cited=[0],
        usage=usage(),
    )

    records += [
        leaked,
        make_record(xfact_row("Crashed."), error=RuntimeError("inference down")),
        make_record(xfact_row("No search."), search_unavailable=True),
        make_record(xfact_row("No model."), llm_unreachable=True),
    ]

    return write_run(directory, records, **kwargs), records


def test_a_report_renders_from_a_fixture_run(tmp_path):

    run_dir, records = fixture_run(tmp_path / "runs" / "fixture" / "stub-model" / ("k" * 12))

    target = write_report(run_dir, resamples=RESAMPLES, root=tmp_path / "reports")

    assert target == tmp_path / "reports" / "fixture" / "stub-model" / ("k" * 12)

    result = json.loads((target / "metrics.json").read_text(encoding="utf-8"))

    # Set apart, by id, and never in the error rate.
    outcomes = result["outcomes"]

    assert outcomes["error"]["count"] == 1
    assert outcomes["searchUnavailable"]["count"] == 1
    assert outcomes["llmUnreachable"]["count"] == 1
    assert outcomes["scored"]["count"] == 11

    # The leaked claim is scored (and right), so it counts in "all
    # scored" and is removed from "without flags": that is the hand-made
    # fixture again.
    scored = result["metrics"]["scored"]
    unflagged = result["metrics"]["scoredUnflagged"]

    assert scored["n"] == 11
    assert scored["accuracy"] == pytest.approx(6 / 11)

    assert unflagged["n"] == 10
    assert unflagged["accuracy"] == 0.5
    assert unflagged["macroF1"] == pytest.approx(47 / 105)
    assert unflagged["kappa"] == pytest.approx(0.28 / 0.78)

    assert result["flags"]["verdictLeak"]["flagged"] == [records[10]["id"]]

    assert result["bootstrap"] == {"seed": 2026, "resamples": RESAMPLES, "level": 0.95}

    assert set(result["breakdowns"]) == {"language", "site"}
    assert result["breakdowns"]["language"]["es"]["n"] == 1

    assert result["usage"]["promptTokens"] == 1000
    assert result["usage"]["cost"] is None

    report = (target / "report.md").read_text(encoding="utf-8")

    for heading in (
        "## Headline", "## What was set apart", "## Per class", "## Confusion matrix",
        "## By language", "## By site", "## Cost, latency and tokens",
    ):
        assert heading in report

    assert "50.0% [" in report  # accuracy without flags, with its interval

    assert json.loads((target / "run.json").read_text(encoding="utf-8"))["key"] == "k" * 12


def test_custom_set_breakdowns_are_by_topic_group_claim_type_and_tier(tmp_path):

    records = [
        make_record(custom_row("fact001", "Uno.", topic="energy", claimType="numerical"), "TRUE"),
        make_record(custom_row("fact002", "Dos.", topic="medicine", claimType="factual", label="FALSE"), "FALSE"),
        make_record(custom_row("fact003", "Tres.", topic="arts", claimType="interpretive",
                               sourceTier="reference_media"), "UNVERIFIED"),
    ]

    run_dir = write_run(tmp_path / "run", records, stem="manual")

    result = json.loads(
        (write_report(run_dir, resamples=RESAMPLES, root=tmp_path / "reports") / "metrics.json")
        .read_text(encoding="utf-8")
    )

    breakdowns = result["breakdowns"]

    assert set(breakdowns) == {"language", "topicGroup", "claimType", "sourceTier"}
    assert set(breakdowns["topicGroup"]) == {"environment", "health", "culture"}
    assert breakdowns["claimType"]["numerical"]["accuracy"] == 1.0
    assert result["flags"]["verdictLeak"]["notApplicable"] == 3


def test_a_priced_run_states_its_cost(tmp_path):

    records = [make_record(xfact_row(f"C{n}."), "TRUE", usage=usage(2_000_000, 500_000)) for n in range(4)]

    run_dir = write_run(tmp_path / "run", records, model="llama-3.1-8b-instant", provider="api.groq.com")

    prices = {"api.groq.com/llama-3.1-8b-instant": {"inputPerMTok": 0.05, "outputPerMTok": 0.08, "asOf": "2026-11-10"}}

    result = json.loads(
        (write_report(run_dir, prices=prices, resamples=RESAMPLES, root=tmp_path / "reports") / "metrics.json")
        .read_text(encoding="utf-8")
    )

    # 4 claims x (2 x 0.05 + 0.5 x 0.08)
    assert result["usage"]["cost"]["total"] == pytest.approx(0.56)
    assert result["usage"]["cost"]["per100Units"] == pytest.approx(14.0)


def test_compare_pairs_two_runs_over_the_claims_both_scored(tmp_path):

    baseline_records = [
        make_record(xfact_row(f"Claim {n}.", label=gold), "UNVERIFIED")
        for n, (gold, _) in enumerate(PAIRS, start=1)
    ]

    # One claim the baseline lost to a search outage: out of both sides.
    baseline_records[0] = make_record(xfact_row("Claim 1.", label="TRUE"), search_unavailable=True)

    baseline = write_run(tmp_path / "a", baseline_records, model="small", key="a" * 12)
    candidate, _ = fixture_run(tmp_path / "b", model="big", key="b" * 12)

    target = write_report(candidate, compare_with=baseline, resamples=RESAMPLES, root=tmp_path / "reports")

    comparison = json.loads((target / "metrics.json").read_text(encoding="utf-8"))["comparison"]

    assert comparison["baseline"]["model"] == "small"
    assert comparison["claims"]["paired"] == 9
    assert comparison["claims"]["setApartOnEitherSide"] == 1
    assert comparison["sameDataset"] is True

    # Claims 2-10: baseline right only on claim 9 (UNVERIFIED); candidate
    # right on 2, 5, 7, 9. So 1/9 against 4/9.
    accuracy = comparison["difference"]["accuracy"]

    assert accuracy["a"] == pytest.approx(1 / 9)
    assert accuracy["b"] == pytest.approx(4 / 9)
    assert accuracy["difference"] == pytest.approx(3 / 9)

    assert comparison["discordant"] == {"onlyA": 0, "onlyB": 3}

    assert "## Paired comparison" in (target / "report.md").read_text(encoding="utf-8")


def test_comparing_a_run_with_itself_differs_by_exactly_zero(tmp_path):

    run_dir, _ = fixture_run(tmp_path / "run")

    target = write_report(run_dir, compare_with=run_dir, resamples=RESAMPLES, root=tmp_path / "reports")

    difference = json.loads((target / "metrics.json").read_text(encoding="utf-8"))["comparison"]["difference"]

    assert all(
        (d["difference"], d["low"], d["high"]) == (0, 0, 0)
        for d in difference.values()
        if d["difference"] is not None
    )


def test_the_models_table_puts_runs_side_by_side_and_refuses_mixed_datasets(tmp_path):

    first, _ = fixture_run(tmp_path / "a", model="llama3.2:3b", key="a" * 12)
    second, _ = fixture_run(tmp_path / "b", model="llama-3.1-8b-instant", key="b" * 12, provider="api.groq.com")

    target = models_table([first, second], resamples=RESAMPLES, root=tmp_path / "reports")

    table = json.loads((target / "models.json").read_text(encoding="utf-8"))

    assert [row["model"] for row in table["runs"]] == ["llama3.2:3b", "llama-3.1-8b-instant"]
    assert "| `llama-3.1-8b-instant` | api.groq.com |" in (target / "models.md").read_text(encoding="utf-8")

    other = write_run(tmp_path / "c", fixture_records(), dataset_sha="e" * 64)

    with pytest.raises(ValueError, match="same dataset"):
        models_table([first, other], resamples=RESAMPLES, root=tmp_path / "reports")


def test_a_run_is_reported_on_its_latest_record_per_claim(tmp_path):
    """An error retried into an ok counts once, as the ok."""

    row = xfact_row("Retried.")

    run_dir = write_run(tmp_path / "run", [
        make_record(row, error=RuntimeError("first try")),
        make_record(row, "TRUE"),
    ])

    run = load_run(run_dir)

    assert len(run.records) == 1
    assert run.records[0]["status"] == "ok"


def test_the_report_command_writes_the_report(tmp_path, capsys):

    run_dir, _ = fixture_run(tmp_path / "run")

    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps({"stub-model": {"inputPerMTok": 0, "outputPerMTok": 0}}), encoding="utf-8")

    status = cli.main([
        "report", "--run", str(run_dir), "--prices", str(prices),
        "--resamples", str(RESAMPLES), "--seed", "5", "--out", str(tmp_path / "reports"),
    ])

    assert status == 0

    target = tmp_path / "reports" / "fixture" / "stub-model" / ("k" * 12)

    result = json.loads((target / "metrics.json").read_text(encoding="utf-8"))

    assert result["bootstrap"]["seed"] == 5
    assert result["usage"]["cost"]["total"] == 0

    assert "## Headline" in capsys.readouterr().out
