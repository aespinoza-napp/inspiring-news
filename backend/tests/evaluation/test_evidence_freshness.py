"""
How new is too new (roadmap P1.2): the newest evidence's age at each
claim, from the set, and verdicts by that age and by the claim's age
when a run checked it.
"""

from __future__ import annotations

import json

import pytest

from src.evaluation import cli
from src.evaluation.dataset import load_dataset, parse_row
from src.evaluation.freshness import bucket, days_between, evidence_age, freshness, render, run_freshness, set_freshness
from src.evaluation.report import load_run

from tests.evaluation.support import custom_row, make_record, source, write_jsonl, write_run


def row(fact_id: str, claim_date: str, evidence_date: str | None, **extra) -> dict:

    return custom_row(fact_id, f"Claim {fact_id}.", claimDate=claim_date, evidenceDate=evidence_date, **extra)


@pytest.mark.parametrize("days, name", [
    (0, "same day"), (1, "1-7 days"), (7, "1-7 days"), (8, "8-30 days"), (30, "8-30 days"),
    (31, "31-365 days"), (365, "31-365 days"), (366, "over a year"), (None, None), (-1, None),
])
def test_the_buckets_include_their_upper_bound(days, name):

    assert bucket(days) == name


def test_the_age_is_whole_days_from_the_evidence_to_the_claim():

    assert evidence_age(parse_row(row("fact001", "2026-09-23", "2026-09-01"))) == 22
    assert evidence_age(parse_row(row("fact002", "2026-09-23", None))) is None

    # A timestamp counts by its day.
    assert days_between("2026-10-20T23:59:00", "2026-10-19") == 1

    # x-fact rows carry no evidence date at all.
    from tests.evaluation.support import xfact_row
    assert parse_row(xfact_row("A claim.", evidenceDate="2020-01-01")).evidence_date is None


def test_the_set_leaves_out_synthetic_claims_and_lists_what_it_cannot_date():

    rows = tuple(parse_row(raw) for raw in [
        row("fact001", "2026-09-23", "2026-09-23"),
        row("fact002", "2026-09-23", "2026-09-20"),
        row("fact003", "2026-09-23", "2024-01-01"),
        row("fact004", "2026-09-23", None),
        # Rule 3 refuses this in the labeller; a hand edit could still leave one.
        row("fact005", "2026-09-23", "2026-09-30"),
        # A synthetic FALSE copies fact001's dates.
        row("fact006", "2026-09-23", "2026-09-23", label="FALSE", mutatedFrom="fact001", mutation="number"),
    ])

    result = set_freshness(rows)

    assert result["mutatedLeftOut"] == 1
    assert result["undated"] == ["fact004"]
    assert result["evidenceAfterClaim"] == ["fact005"]
    assert result["sameDayIds"] == ["fact001"]

    everything = result["all"]

    assert everything["n"] == 3
    assert everything["median"] == 3.0
    assert {name: b["count"] for name, b in everything["buckets"].items()} == {
        "same day": 1, "1-7 days": 1, "8-30 days": 0, "31-365 days": 0, "over a year": 1,
    }
    assert result["by"]["language"]["es"]["n"] == 3


def _records():
    """Three scored claims checked on 2026-10-01, one set apart, one from another set."""

    def made(fact_id, verdict, *, evidence=True, **kwargs):
        record = make_record(
            row(fact_id, *DATES[fact_id]), verdict,
            evidence=[source("https://ine.es/a")] if evidence else [], **kwargs,
        )
        record["startedAt"] = "2026-10-01T10:00:00"
        return record

    return [
        made("fact001", "TRUE"),                          # claim 8 days old, evidence same day
        made("fact002", "UNVERIFIED", evidence=False),    # claim 1 day old, evidence 3 days older
        made("fact003", "TRUE"),                          # claim 100 days old, evidence 2 years older
        made("fact004", "UNVERIFIED", search_unavailable=True),
        {**made("fact001", "TRUE"), "id": "elsewhere"},
    ]


DATES = {
    "fact001": ("2026-09-23", "2026-09-23"),
    "fact002": ("2026-09-30", "2026-09-27"),
    "fact003": ("2026-06-23", "2024-06-01"),
    "fact004": ("2026-09-23", "2026-09-01"),
}


def _rows():

    return tuple(parse_row(row(fact_id, *dates)) for fact_id, dates in DATES.items())


def test_a_run_is_joined_to_the_set_and_split_by_both_ages():

    result = run_freshness(_records(), _rows(), seed=7, resamples=50)

    assert result["scored"] == 3
    assert result["setApart"] == 1
    assert result["notInDataset"] == 1

    at_run = result["claimAgeAtRun"]

    assert (at_run["min"], at_run["median"], at_run["max"]) == (1, 8.0, 100)
    assert at_run["buckets"]["1-7 days"]["n"] == 1
    assert at_run["buckets"]["1-7 days"]["withEvidence"] == 0.0
    assert at_run["buckets"]["1-7 days"]["unverified"] == 1.0
    assert at_run["buckets"]["8-30 days"]["accuracy"] == 1.0

    by_evidence = result["evidenceAge"]["buckets"]

    assert by_evidence["same day"]["n"] == 1
    assert by_evidence["1-7 days"]["accuracy"] == 0.0
    assert by_evidence["over a year"]["n"] == 1


def test_the_cli_writes_the_report_with_each_run(tmp_path, capsys):

    dataset = tmp_path / "manual"
    dataset.mkdir()

    for fact_id, dates in DATES.items():
        (dataset / f"{fact_id}.json").write_text(json.dumps(row(fact_id, *dates)), encoding="utf-8")

    run = write_run(tmp_path / "run", _records())

    code = cli.main([
        "freshness", "--dataset", str(dataset), "--run", str(run),
        "--resamples", "50", "--out", str(tmp_path / "reports"),
    ])

    assert code == 0

    target = tmp_path / "reports" / "manual"

    markdown = (target / "freshness.md").read_text(encoding="utf-8")

    assert "## The set" in markdown
    assert "| All | 4 |" in markdown
    assert "Claim's age when checked" in markdown
    assert json.loads((target / "freshness.json").read_text(encoding="utf-8"))["runs"][0]["scored"] == 3


def test_a_jsonl_set_works_and_a_set_without_runs_renders(tmp_path):

    path = write_jsonl(tmp_path / "set.jsonl", [row(fact_id, *dates) for fact_id, dates in DATES.items()])

    result = freshness(load_dataset(path), seed=7, resamples=50)

    assert result["runs"] == []
    assert "## Run" not in render(result)
