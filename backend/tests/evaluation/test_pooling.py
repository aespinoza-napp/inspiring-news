"""
Pooled relevance judgements (src/evaluation/pooling.py): every variant's
top pages pooled once, judged once, and every variant scored on the same
judgements.
"""

from __future__ import annotations

import json

import pytest

from src.evaluation import cli
from src.evaluation.pooling import judge, load_judgements, pool, pooled_table, save_judgements
from src.evaluation.report import load_run

from tests.evaluation.support import custom_row, make_record, source, write_run

BOOT = {"seed": 7, "resamples": 200}


def record(fact_id: str, ranked: list[str], **kwargs) -> dict:

    return make_record(custom_row(fact_id, f"Claim {fact_id}."), "TRUE", evidence=[source(url) for url in ranked], **kwargs)


def run(tmp_path, name: str, records: list[dict]):

    directory = write_run(tmp_path / name, records, key=name * 3)
    manifest = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    manifest["label"] = name
    (directory / "run.json").write_text(json.dumps(manifest), encoding="utf-8")
    return load_run(directory)


def variants(tmp_path):
    """Two variants over two claims; one page the same under two spellings."""

    a = run(tmp_path, "anchor", [
        record("fact001", ["https://ine.es/a", "https://x.org/1"]),
        record("fact002", ["https://y.org/2"]),
    ])
    b = run(tmp_path, "all", [
        record("fact001", ["https://www.ine.es/a/", "https://z.org/3"]),
        record("fact002", ["https://y.org/2", "https://w.org/4"]),
        # Its search failed: nothing of it is pooled or scored.
        record("fact003", ["https://never.org/"], search_unavailable=True),
    ])
    return a, b


# ----------------------------------------------------------------------
# The pool
# ----------------------------------------------------------------------


def test_each_page_is_pooled_once_however_it_was_spelled(tmp_path):

    a, b = variants(tmp_path)

    entries, added = pool([a, b], [])

    assert added == 5
    keyed = {(entry["claimId"], entry["key"]): entry for entry in entries}
    assert keyed[("fact001", "ine.es/a")]["pooledFrom"] == ["anchor", "all"]
    assert keyed[("fact002", "w.org/4")]["pooledFrom"] == ["all"]
    assert all(entry["relevant"] is None for entry in entries)
    assert not any(entry["claimId"] == "fact003" for entry in entries)


def test_pooling_again_keeps_every_judgement_and_adds_only_new_pages(tmp_path):

    a, b = variants(tmp_path)

    entries, _ = pool([a], [])
    for entry in entries:
        entry["relevant"] = entry["key"] == "ine.es/a"

    entries, added = pool([a, b], entries)

    assert added == 2
    keyed = {entry["key"]: entry for entry in entries}
    assert keyed["ine.es/a"]["relevant"] is True and keyed["ine.es/a"]["pooledFrom"] == ["anchor", "all"]
    assert keyed["x.org/1"]["relevant"] is False
    assert keyed["z.org/3"]["relevant"] is None


def test_the_depth_bounds_what_is_pooled(tmp_path):

    a, _ = variants(tmp_path)

    entries, _ = pool([a], [], depth=1)

    assert sorted(entry["key"] for entry in entries) == ["ine.es/a", "y.org/2"]


# ----------------------------------------------------------------------
# Scores
# ----------------------------------------------------------------------


def judged_pool(tmp_path):

    a, b = variants(tmp_path)
    entries, _ = pool([a, b], [])
    marks = {"ine.es/a": True, "x.org/1": False, "z.org/3": True, "y.org/2": False}
    for entry in entries:
        # w.org/4 is left unjudged: it counts only in coverage.
        entry["relevant"] = marks.get(entry["key"])
    return a, b, entries


def test_scores_worked_out_by_hand(tmp_path):
    """
    fact001: relevant in the pool ine.es/a and z.org/3 (2); fact002: none.

    anchor: fact001 ranks ine.es/a (rel), x.org/1 (not) -> P 1/2, R 1/2, MRR 1, judged 1
            fact002 ranks y.org/2 (not)                 -> P 0, R and MRR undefined, judged 1
    all:    fact001 ranks ine.es/a, z.org/3 (both rel)  -> P 1, R 1, MRR 1, judged 1
            fact002 ranks y.org/2 (not), w.org/4 (?)    -> P 0/1, R and MRR undefined, judged 1/2
    """

    a, b, entries = judged_pool(tmp_path)

    table = pooled_table([a, b], entries, **BOOT)

    assert table["pool"] == {"pages": 5, "judged": 4, "relevant": 2, "claims": 2, "claimsWithRelevant": 1}

    anchor, every = (row["metrics"] for row in table["runs"])

    assert anchor["precision"]["value"] == 0.25
    assert anchor["recall"]["value"] == 0.5 and anchor["recall"]["n"] == 1
    assert anchor["mrr"]["value"] == 1.0
    assert anchor["judged"]["value"] == 1.0

    assert every["precision"]["value"] == 0.5
    assert every["recall"]["value"] == 1.0
    assert every["judged"]["value"] == 0.75

    vs = table["runs"][1]["vsBaseline"]
    assert vs["recall"]["difference"] == 0.5 and vs["recall"]["pairs"] == 1
    assert vs["precision"]["pairs"] == 2


def test_the_cli_pools_and_scores(tmp_path, capsys):

    a, b = variants(tmp_path)
    judgements = tmp_path / "judgements" / "set.jsonl"

    assert cli.main(["pool", "--run", str(a.directory), "--run", str(b.directory), "--judgements", str(judgements)]) == 0
    assert "5 new page(s) pooled" in capsys.readouterr().out

    entries = load_judgements(judgements)
    for entry in entries:
        entry["relevant"] = entry["key"] in ("ine.es/a", "z.org/3")
    save_judgements(judgements, entries)

    assert cli.main([
        "pooled", "--run", str(a.directory), "--run", str(b.directory), "--judgements", str(judgements),
        "--resamples", "50", "--out", str(tmp_path / "reports"),
    ]) == 0

    markdown = (tmp_path / "reports" / "fixture" / "pooled.md").read_text(encoding="utf-8")
    assert "| anchor |" in markdown and "| all - anchor |" not in markdown
    assert "| Run - anchor |" in markdown


# ----------------------------------------------------------------------
# Judging
# ----------------------------------------------------------------------


def test_judging_saves_each_answer_and_resumes_where_it_stopped(tmp_path):

    a, b = variants(tmp_path)
    path = tmp_path / "judgements.jsonl"
    entries, _ = pool([a, b], [])
    save_judgements(path, entries)

    answers = iter(["y", "maybe", "n", "s", "q"])
    said = []

    result = judge(path, ask=lambda prompt: next(answers), say=said.append)

    # y and n judged ("maybe" asked again), s skipped, q stopped.
    assert result == {"judged": 2, "left": 3}
    marks = [entry["relevant"] for entry in load_judgements(path)]
    assert marks[:2] == [True, False] and marks[2:] == [None, None, None]

    # The next session starts at the first unjudged page, the skipped one included.
    result = judge(path, ask=lambda prompt: "n", say=said.append)
    assert result == {"judged": 3, "left": 0}


@pytest.mark.parametrize("missing", [True, False])
def test_an_absent_or_empty_judgement_file_is_an_empty_pool(tmp_path, missing):

    path = tmp_path / "j.jsonl"
    if not missing:
        path.write_text("\n", encoding="utf-8")

    assert load_judgements(path) == []
