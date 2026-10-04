"""
Retrieval metrics and strategy comparison (src/evaluation/retrieval.py),
over records built by record.py itself, with values worked out by hand.
Plus the retrieval-only run mode and the run key's label. Nothing live.
"""

import json

import pytest

from src.config.thresholds import PipelineThresholds
from src.evaluation import cli
from src.evaluation.report import evaluate, load_run, models_table, render, retrieval_table
from src.evaluation.retrieval import (
    claim_retrieval,
    compare_retrieval,
    references,
    retrieval_metrics,
)
from src.evaluation.runner import (
    RETRIEVAL,
    RETRIEVAL_ONLY_EXPLANATION,
    RetrievalOnlyVerifier,
    run_key,
)
from src.models.core.claim import Claim
from src.models.fact_checker.evidence import EvidenceOrigin, RejectedEvidence
from src.models.fact_checker.fact_check import Verdict
from src.models.fact_checker.pipeline_stage import PipelineStage

from tests.evaluation.support import custom_row, make_record, source, write_run, xfact_row

BOOT = {"seed": 7, "resamples": 200}


def cut(url: str, stage=PipelineStage.EVIDENCE_RANKING, reason="below the pertinence gate") -> RejectedEvidence:

    return RejectedEvidence(url=url, title=url, origin=EvidenceOrigin.WEB, stage=stage, reason=reason)


def record(claim_id: str, refs: list[str], ranked: list[str], *, rejected=(), cited=(), **row):

    raw = xfact_row(f"Claim {claim_id}.", referenceEvidenceLinks=refs, **row)
    made = make_record(raw, "TRUE", evidence=[source(url) for url in ranked], cited=list(cited), rejected=list(rejected))
    made["id"] = claim_id
    return made


# ----------------------------------------------------------------------
# The reference set
# ----------------------------------------------------------------------


def test_a_reference_matches_however_the_engine_spelled_it():

    rec = record(
        "c1",
        refs=["https://www.Example.org/Report/?utm_source=x"],
        ranked=["http://example.org/report/"],
    )

    values = claim_retrieval(rec)["values"]

    assert values["linkRecall@ranked"] == 1.0
    assert values["linkMRR"] == 1.0


def test_the_fact_checkers_own_verdict_page_is_not_a_reference():
    """x-fact: a link on the row's own site is the published verdict."""

    rec = record(
        "c1",
        refs=["https://chequeado.com/verificacion/x", "https://indec.gob.ar/informe"],
        ranked=["https://chequeado.com/verificacion/x"],
        site="chequeado.com",
    )

    links, domains, self_links = references(rec)

    assert links == {"indec.gob.ar/informe"}
    assert domains == {"indec.gob.ar"}
    assert self_links == 1

    values = claim_retrieval(rec)["values"]

    # Finding the verdict page is a leak, not a hit.
    assert values["linkRecall@ranked"] == 0.0
    assert values["verdictLeak"] == 1.0


def test_on_the_custom_set_the_articles_own_site_is_an_ordinary_reference():

    raw = custom_row("fact001", "Uno.", site="elpais.com", referenceEvidenceLinks=["https://elpais.com/a"])
    rec = make_record(raw, "TRUE", evidence=[source("https://elpais.com/a")])

    assert references(rec)[2] == 0
    assert claim_retrieval(rec)["values"]["linkRecall@ranked"] == 1.0
    assert claim_retrieval(rec)["values"]["verdictLeak"] is None


# ----------------------------------------------------------------------
# Depths, ranks and cuts
# ----------------------------------------------------------------------


def test_a_reference_the_gate_cut_counts_among_candidates_but_not_ranked():

    rec = record(
        "c1",
        refs=["https://ref.org/a"],
        ranked=["https://other.org/x", "https://ref.org/b"],
        rejected=[cut("https://ref.org/a")],
        cited=[0],
    )

    claim = claim_retrieval(rec)
    values = claim["values"]

    assert values["linkRecall@candidates"] == 1.0
    assert values["linkRecall@ranked"] == 0.0
    assert values["linkRecall@cited"] == 0.0

    # The domain survived through another page, second in the ranking.
    assert values["domainRecall@ranked"] == 1.0
    assert values["domainMRR"] == 0.5
    assert values["domainRecall@cited"] == 0.0

    assert claim["referencesCut"] == ["evidence_ranking: below the pertinence gate"]

    # One of three that reached ranking was cut there.
    assert values["gateCut"] == pytest.approx(1 / 3)
    assert values["candidates"] == 3.0
    assert values["uniqueDomains"] == 2.0


def test_the_run_metrics_against_values_worked_out_by_hand():
    """
    c1 finds its reference first; c2 finds it third; c3 finds nothing and
    has no evidence; c4 has no references; c5's search failed.
    linkRecall@ranked = 2/3, linkMRR = (1 + 1/3 + 0) / 3 = 0.4444,
    hasEvidence over the 4 searched = 3/4.
    """

    records = [
        record("c1", ["https://a.org/1"], ["https://a.org/1"]),
        record("c2", ["https://b.org/1"], ["https://x.org/1", "https://y.org/1", "https://b.org/1"]),
        record("c3", ["https://c.org/1"], []),
        record("c4", [], ["https://z.org/1"]),
    ]

    failed = record("c5", ["https://e.org/1"], [])
    failed["searchUnavailable"] = True
    records.append(failed)

    section = retrieval_metrics(records, **BOOT)

    assert section["claims"] == {
        "total": 5, "searched": 4, "withReferences": 3,
        "searchUnavailable": 1, "errors": 0, "selfLinksRemoved": 0, "referencesUnavailable": 0,
    }

    gold = section["gold"]
    assert gold["linkRecall@ranked"]["value"] == pytest.approx(2 / 3, abs=1e-4)
    assert gold["linkMRR"]["value"] == pytest.approx((1 + 1 / 3) / 3, abs=1e-4)
    assert gold["linkRecall@ranked"]["low"] <= gold["linkRecall@ranked"]["value"] <= gold["linkRecall@ranked"]["high"]

    assert section["goldFree"]["hasEvidence"]["value"] == 0.75
    assert section["medians"]["ranked"] == 1.0

    assert section["groups"]["language"]["en"]["claims"] == 4


def test_which_query_found_the_ranked_sources_is_counted():

    rec = record("c1", [], ["https://a.org/1", "https://b.org/1"])
    rec["evidence"][0]["foundBy"] = ["anchor", "proposition"]
    rec["evidence"][1]["foundBy"] = ["refutation"]

    assert retrieval_metrics([rec], **BOOT)["foundBy"] == {"anchor": 1, "proposition": 1, "refutation": 1}


# ----------------------------------------------------------------------
# Two strategies
# ----------------------------------------------------------------------


def two_strategies():

    baseline = [
        record("c1", ["https://a.org/1"], []),
        record("c2", ["https://b.org/1"], ["https://b.org/1"]),
        record("c3", ["https://c.org/1"], []),
    ]

    candidate = [
        record("c1", ["https://a.org/1"], ["https://a.org/1"]),
        record("c2", ["https://b.org/1"], ["https://b.org/1"]),
        record("c3", ["https://c.org/1"], ["https://c.org/1"]),
    ]

    return baseline, candidate


def test_strategies_are_paired_claim_by_claim():

    baseline, candidate = two_strategies()

    comparison = compare_retrieval(baseline, candidate, **BOOT)

    recall = comparison["differences"]["linkRecall@ranked"]

    assert comparison["pairedClaims"] == 3
    assert (recall["baseline"], recall["candidate"]) == (pytest.approx(1 / 3, abs=1e-4), 1.0)
    assert recall["difference"] == pytest.approx(2 / 3, abs=1e-4)
    assert (recall["onlyBaseline"], recall["onlyCandidate"]) == (0, 2)


def test_a_claim_whose_search_failed_on_one_side_is_left_out_of_both():

    baseline, candidate = two_strategies()
    baseline[0]["searchUnavailable"] = True

    comparison = compare_retrieval(baseline, candidate, **BOOT)

    assert comparison["pairedClaims"] == 2
    assert comparison["differences"]["linkRecall@ranked"]["pairs"] == 2


def test_the_retrieval_table_compares_runs_and_names_their_strategies(tmp_path):

    baseline, candidate = two_strategies()

    a = write_run(tmp_path / "a", baseline, key="a" * 12)
    b = write_run(tmp_path / "b", candidate, key="b" * 12)

    manifest = json.loads((b / "run.json").read_text(encoding="utf-8"))
    manifest.update(label="no-gate", mode=RETRIEVAL, thresholdsOverridden={"evidence_min_pertinence": 0.0})
    (b / "run.json").write_text(json.dumps(manifest), encoding="utf-8")

    target = retrieval_table([a, b], seed=7, resamples=100, root=tmp_path / "reports")

    markdown = (target / "retrieval.md").read_text(encoding="utf-8")

    assert "`no-gate`: retrieval run, thresholds evidence_min_pertinence=0.0" in markdown
    assert "### Retrieval: no-gate" in markdown
    assert "+66.7 pts" in markdown

    table = json.loads((target / "retrieval.json").read_text(encoding="utf-8"))
    assert [row["strategy"]["label"] for row in table["runs"]] == [None, "no-gate"]


def test_the_cli_writes_the_retrieval_table(tmp_path, capsys):

    baseline, candidate = two_strategies()

    a = write_run(tmp_path / "a", baseline, key="a" * 12)
    b = write_run(tmp_path / "b", candidate, key="b" * 12)

    assert cli.main(["retrieval", "--run", str(a), "--run", str(b), "--resamples", "50",
                     "--out", str(tmp_path / "out")]) == 0

    assert (tmp_path / "out" / "fixture" / "retrieval.md").exists()


# ----------------------------------------------------------------------
# Reports and the retrieval-only mode
# ----------------------------------------------------------------------


def test_every_report_has_a_retrieval_section(tmp_path):

    run = load_run(write_run(tmp_path / "run", two_strategies()[1]))

    result = evaluate(run, seed=7, resamples=100)

    assert result["retrieval"]["gold"]["linkRecall@ranked"]["value"] == 1.0
    assert "## Retrieval" in render(result)
    assert "## Headline" in render(result)


def test_a_retrieval_only_report_has_no_verdict_metrics(tmp_path):

    directory = write_run(tmp_path / "run", two_strategies()[1])

    manifest = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    manifest["mode"] = RETRIEVAL
    (directory / "run.json").write_text(json.dumps(manifest), encoding="utf-8")

    markdown = render(evaluate(load_run(directory), seed=7, resamples=100))

    assert "retrieval only" in markdown
    assert "## Retrieval" in markdown
    assert "## Headline" not in markdown and "Accuracy" not in markdown

    with pytest.raises(ValueError, match="use `cli retrieval`"):
        models_table([directory], root=tmp_path / "reports")


def test_the_retrieval_only_verifier_answers_without_a_model():

    result = RetrievalOnlyVerifier().verify(Claim(text="A claim.", entities={}, confidence=0.9), [])

    assert result.verdict == Verdict.UNVERIFIED
    assert result.explanation == RETRIEVAL_ONLY_EXPLANATION
    assert result.llm_unreachable is False


def test_the_mode_and_the_label_key_a_run_only_when_set():
    """A full, unlabelled run keeps the key it had before either existed."""

    thresholds = PipelineThresholds()
    weights = {"W": 1.0}

    plain = run_key("d" * 64, "m", thresholds, "snapshot", weights)

    assert run_key("d" * 64, "m", thresholds, "snapshot", weights, mode="full", label=None) == plain
    assert run_key("d" * 64, "m", thresholds, "snapshot", weights, mode=RETRIEVAL) != plain
    assert run_key("d" * 64, "m", thresholds, "snapshot", weights, label="no-ddg") != plain
    assert run_key("d" * 64, "m", thresholds, "snapshot", weights, label="a") != run_key(
        "d" * 64, "m", thresholds, "snapshot", weights, label="b"
    )


def test_the_run_command_passes_the_mode_and_the_label(monkeypatch, tmp_path, capsys):

    from tests.evaluation.support import write_jsonl

    seen = {}

    def build(config):
        seen["config"] = config
        raise SystemExit(0)

    monkeypatch.setattr(cli, "build_runner", build)

    dataset = write_jsonl(tmp_path / "pilot.jsonl", [xfact_row("A claim.")])

    with pytest.raises(SystemExit):
        cli.main(["run", "--dataset", str(dataset), "--retrieval-only", "--label", "baseline",
                  "--root", str(tmp_path / "runs")])

    config = seen["config"]

    assert (config.mode, config.label, config.model) == (RETRIEVAL, "baseline", "retrieval-only")
    assert config.directory.parent.name == "retrieval-only"


def test_placeholder_references_are_counted_as_unavailable_not_missed():
    """Every PolitiFact row in the pilot has only "<LINK NOT AVAILABLE>"."""

    rec = record("c1", ["<LINK NOT AVAILABLE>", "<LINK NOT AVAILABLE>"], ["https://a.org/1"])

    claim = claim_retrieval(rec)

    assert (claim["hasReferences"], claim["placeholders"]) == (False, 2)
    assert "linkRecall@ranked" not in claim["values"]

    section = retrieval_metrics([rec], **BOOT)

    assert section["claims"]["referencesUnavailable"] == 1
    assert section["gold"]["linkRecall@ranked"]["n"] == 0
