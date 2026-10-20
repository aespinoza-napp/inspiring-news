"""
Journalist effort, the harness's half (docs/decisions/evaluation.md
§Journalist effort): usable without re-checking, confidently wrong, and
the estimate built from them.
"""

from __future__ import annotations

import pytest

from src.evaluation import cli
from src.evaluation.effort import confidently_wrong, effort_metrics, usable
from src.evaluation.report import evaluate, load_run, render
from src.models.fact_checker.evidence import EvidenceStance

from tests.evaluation.support import custom_row, make_record, source, write_run

BOOT = {"seed": 7, "resamples": 200}


def claim(fact_id: str, verdict: str, *, label: str = "TRUE", stance=EvidenceStance.SUPPORTS, cited=True,
          published: str | None = "2026-09-01", **kwargs) -> dict:

    evidence = [source("https://ine.es/a", published=published).model_copy(update={"stance": stance})]

    return make_record(
        custom_row(fact_id, f"Claim {fact_id}.", label=label),
        verdict, evidence=evidence, cited=[0] if cited else [], **kwargs,
    )


def test_usable_needs_gold_a_definitive_verdict_a_cited_stance_and_no_leak():

    assert usable(claim("fact001", "TRUE"))
    assert usable(claim("fact002", "FALSE", label="FALSE", stance=EvidenceStance.CONTRADICTS))

    assert not usable(claim("fact003", "FALSE"))                                  # wrong
    assert not usable(claim("fact004", "UNVERIFIED", label="UNVERIFIED"))         # right, but says nothing
    assert not usable(claim("fact005", "TRUE", stance=EvidenceStance.UNRELATED))  # cites nothing on point
    assert not usable(claim("fact006", "TRUE", cited=False))                      # cites nothing at all
    # A cited source newer than the claim (2026-09-23): the temporal leak flag.
    assert not usable(claim("fact007", "TRUE", published="2026-10-01"))


def test_confidently_wrong_is_a_definitive_verdict_that_is_not_gold():

    assert confidently_wrong(claim("fact001", "FALSE"))
    assert confidently_wrong(claim("fact002", "TRUE", label="UNVERIFIED"))

    assert not confidently_wrong(claim("fact003", "UNVERIFIED"))
    assert not confidently_wrong(claim("fact004", "TRUE"))


def records() -> list[dict]:

    return [
        claim("fact001", "TRUE"),
        claim("fact002", "TRUE"),
        claim("fact003", "FALSE"),
        claim("fact004", "UNVERIFIED"),
        claim("fact005", "TRUE", stance=EvidenceStance.UNRELATED),
        # Set apart: never counted, whatever it says.
        claim("fact006", "FALSE", search_unavailable=True),
    ]


def test_shares_over_the_scored_claims_with_ids_and_intervals():

    section = effort_metrics(records(), **BOOT)

    assert section["scored"] == 5
    assert section["usable"]["count"] == 2
    assert section["usable"]["share"] == 0.4
    assert section["usable"]["ids"] == ["fact001", "fact002"]
    assert section["usable"]["low"] <= 0.4 <= section["usable"]["high"]
    assert section["confidentlyWrong"]["ids"] == ["fact003"]
    assert section["rightButUnsupported"] == 1
    assert section["estimate"] is None


def test_the_estimate_needs_the_minutes_a_person_takes():

    section = effort_metrics(records(), minutes_per_fact=10.0, **BOOT)

    assert section["estimate"]["minutesSavedPer100"] == 400.0
    assert section["estimate"]["confidentlyWrongPer100"] == 20.0
    assert section["estimate"]["minutesSavedPer100Low"] <= 400.0 <= section["estimate"]["minutesSavedPer100High"]


def test_every_report_has_the_section_and_the_cli_passes_the_minutes(tmp_path, capsys):

    directory = write_run(tmp_path / "run", records())

    markdown = render(evaluate(load_run(directory), seed=7, resamples=50))

    assert "## Journalist effort" in markdown
    assert "No effort estimate" in markdown

    code = cli.main([
        "report", "--run", str(directory), "--minutes-per-fact", "10",
        "--resamples", "50", "--out", str(tmp_path / "reports"),
    ])

    assert code == 0
    assert "400.0 minutes saved per 100 claims" in capsys.readouterr().out


@pytest.mark.parametrize("value", ["ten", "-"])
def test_minutes_must_be_a_number(value, tmp_path):

    with pytest.raises(SystemExit):
        cli.main(["report", "--run", str(tmp_path), "--minutes-per-fact", value])
