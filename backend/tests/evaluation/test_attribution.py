"""
Stage attribution (docs/decisions/evaluation.md §Stage attribution):
every wrong verdict to one stage, by the annotator's references and by
the trace alone, from records built with record.py.
"""

from __future__ import annotations

import json

from src.evaluation.attribution import (
    AGGREGATION,
    RANKING,
    REASONING,
    RETRIEVAL,
    attribution_metrics,
    by_reference,
    by_trace,
)
from src.evaluation.report import evaluate, load_run, render
from src.evaluation.runner import ORACLE
from src.models.fact_checker.evidence import EvidenceOrigin, RejectedEvidence
from src.models.fact_checker.pipeline_stage import PipelineStage

from tests.evaluation.support import make_record, source, write_run, xfact_row

REFERENCE = "https://ine.es/informe"


def cut(url: str, reason: str = "below the pertinence gate") -> RejectedEvidence:

    return RejectedEvidence(
        url=url, title=url, origin=EvidenceOrigin.WEB, stage=PipelineStage.EVIDENCE_RANKING, reason=reason,
    )


def wrong(claim_id: str, verdict: str, *, raw: str | None = None, ranked=(), rejected=(),
          refs=(REFERENCE,), label: str = "TRUE", **kwargs) -> dict:
    """A claim with gold `label` (TRUE unless said) and the given trace."""

    row = xfact_row(f"Claim {claim_id}.", label=label, referenceEvidenceLinks=list(refs), site="chequeado.com")

    made = make_record(
        row, verdict, raw_verdict=raw,
        evidence=[source(url) for url in ranked], rejected=list(rejected), **kwargs,
    )
    made["id"] = claim_id

    return made


# ----------------------------------------------------------------------
# One stage per rule
# ----------------------------------------------------------------------


def test_nothing_found_is_retrieval_under_both_rules():

    record = wrong("c1", "UNVERIFIED", raw="UNVERIFIED")

    assert by_trace(record) == RETRIEVAL
    assert by_reference(record) == RETRIEVAL


def test_found_then_all_cut_is_ranking_under_both_rules():

    record = wrong("c1", "UNVERIFIED", raw="UNVERIFIED", rejected=[cut(REFERENCE)])

    assert by_trace(record) == RANKING
    assert by_reference(record) == RANKING


def test_the_reference_ranked_and_misread_is_reasoning_under_both_rules():

    record = wrong("c1", "FALSE", ranked=[REFERENCE])

    assert by_trace(record) == REASONING
    assert by_reference(record) == REASONING


def test_another_page_of_the_references_site_counts_as_found():
    """Domain hits count, as in retrieval.py: the annotator's source, or its site."""

    record = wrong("c1", "FALSE", ranked=["https://ine.es/otra-tabla"])

    assert by_reference(record) == REASONING


def test_a_right_model_verdict_changed_by_the_scorer_is_aggregation_under_both_rules():
    """
    rawVerdict was gold; ConfidenceScorer forced UNVERIFIED. Tested first:
    nothing upstream caused the error, even with no reference found.
    """

    found = wrong("c1", "UNVERIFIED", raw="TRUE", ranked=[REFERENCE])
    not_found = wrong("c2", "UNVERIFIED", raw="TRUE", ranked=["https://other.org/x"])

    for record in (found, not_found):
        assert by_trace(record) == AGGREGATION
        assert by_reference(record) == AGGREGATION


# ----------------------------------------------------------------------
# Where the two columns part
# ----------------------------------------------------------------------


def test_misreading_sources_other_than_the_annotators_is_retrieval_by_reference():
    """The trace says the model misread; the references, that it never saw them."""

    record = wrong("c1", "FALSE", ranked=["https://other.org/x"])

    assert by_trace(record) == REASONING
    assert by_reference(record) == RETRIEVAL

    section = attribution_metrics([record])

    assert section["disagreements"] == [{"id": "c1", "trace": REASONING, "reference": RETRIEVAL}]


def test_a_cut_reference_is_ranking_by_reference_though_something_else_was_ranked():

    record = wrong("c1", "FALSE", ranked=["https://other.org/x"], rejected=[cut(REFERENCE, "same domain")])

    assert by_trace(record) == REASONING
    assert by_reference(record) == RANKING

    section = attribution_metrics([record])

    # Only the reference's own cut explains the reference column.
    assert section["reference"]["rankingCuts"] == {"evidence_ranking: same domain": 1}


def test_a_row_with_only_placeholders_or_the_verdict_page_has_no_reference_column():

    placeholders = wrong("c1", "FALSE", ranked=["https://other.org/x"], refs=["<LINK NOT AVAILABLE>"])
    verdict_page = wrong("c2", "FALSE", refs=["https://chequeado.com/verificacion/x"])

    for record in (placeholders, verdict_page):
        assert by_reference(record) is None

    section = attribution_metrics([placeholders, verdict_page])

    assert section["noReference"] == ["c1", "c2"]
    assert section["reference"]["judged"] == 0
    assert section["trace"]["judged"] == 2
    assert section["bothJudged"] == 0


# ----------------------------------------------------------------------
# A run
# ----------------------------------------------------------------------


def run_records() -> list[dict]:

    return [
        wrong("retrieval", "UNVERIFIED", raw="UNVERIFIED"),
        wrong("ranking", "UNVERIFIED", raw="UNVERIFIED", rejected=[cut(REFERENCE)]),
        wrong("reasoning", "FALSE", ranked=[REFERENCE]),
        wrong("aggregation", "UNVERIFIED", raw="TRUE", ranked=[REFERENCE]),
        wrong("parted", "FALSE", ranked=["https://other.org/x"]),
        # Right: not attributed.
        wrong("right", "TRUE", ranked=[REFERENCE]),
        # Set apart, wrong as they are: never attributed.
        wrong("outage", "UNVERIFIED", raw="UNVERIFIED", search_unavailable=True),
        wrong("no-llm", "UNVERIFIED", raw="UNVERIFIED", ranked=[REFERENCE], llm_unreachable=True),
        wrong("crash", "UNVERIFIED", error=RuntimeError("boom")),
    ]


def test_counts_shares_and_ids_per_stage():

    section = attribution_metrics(run_records())

    assert section["wrong"] == 5

    trace = section["trace"]["stages"]
    reference = section["reference"]["stages"]

    assert {stage: block["ids"] for stage, block in trace.items()} == {
        RETRIEVAL: ["retrieval"],
        RANKING: ["ranking"],
        REASONING: ["reasoning", "parted"],
        AGGREGATION: ["aggregation"],
    }
    assert reference[RETRIEVAL]["ids"] == ["retrieval", "parted"]
    assert reference[REASONING]["ids"] == ["reasoning"]

    assert trace[REASONING]["share"] == 0.4
    assert sum(block["count"] for block in reference.values()) == 5

    assert section["trace"]["rankingCuts"] == {"evidence_ranking: below the pertinence gate": 1}
    assert section["bothJudged"] == 5
    assert [d["id"] for d in section["disagreements"]] == ["parted"]


def test_claims_set_apart_are_never_attributed():

    section = attribution_metrics(run_records())

    attributed = {
        claim_id
        for column in ("trace", "reference")
        for block in section[column]["stages"].values()
        for claim_id in block["ids"]
    }

    assert not attributed & {"outage", "no-llm", "crash", "right"}


def test_every_report_has_a_stage_attribution_section(tmp_path):

    run = load_run(write_run(tmp_path / "run", run_records()))

    result = evaluate(run, seed=7, resamples=50)
    markdown = render(result)

    assert result["attribution"]["wrong"] == 5
    assert "## Stage attribution" in markdown
    assert "| reasoning | 2 (40.0%) | 1 (20.0%) |" in markdown
    assert "| parted | reasoning | retrieval |" in markdown

    # metrics.json is written with json.dumps: the section must survive it.
    json.dumps(result)


def test_an_oracle_report_has_no_reference_column(tmp_path):

    directory = write_run(tmp_path / "run", run_records())

    manifest = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    manifest["mode"] = ORACLE
    (directory / "run.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = evaluate(load_run(directory), seed=7, resamples=50)

    assert result["attribution"]["oracle"] is True
    assert result["attribution"]["reference"]["judged"] == 0

    markdown = render(result)

    assert "No reference column" in markdown
    assert "By reference" not in markdown


def test_a_report_written_before_attribution_still_renders(tmp_path):

    result = evaluate(load_run(write_run(tmp_path / "run", run_records())), seed=7, resamples=50)
    del result["attribution"]

    assert "## Stage attribution" not in render(result)
