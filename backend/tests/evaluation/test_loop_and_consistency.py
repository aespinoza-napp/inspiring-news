"""
The two reports added with the train/test split: what the tuning loop
found (`cli loop`), and whether the pipeline gives the same verdict twice
(`cli consistency`). Every figure is worked out in the comments.
"""

from src.evaluation.consistency import consistency, jaccard, render_consistency, write_consistency
from src.evaluation.loop import loop_report, render_loop, write_loop_report
from src.evaluation.report import load_run

from tests.evaluation.support import custom_row, make_record, source, write_run

BOOT = {"seed": 7, "resamples": 200}


def looped(fact_id, gold, first, *, second=None, trigger=None, outcome="agreed", reference=None):

    record = make_record(custom_row(fact_id, f"Claim {fact_id}.", label=gold), first)

    record["loop"] = {
        "firstVerdict": first,
        "disagrees": first != gold,
        "trigger": trigger,
        "secondLook": {"verdict": second, "evidence": []} if second else None,
        "reference": {"verdict": reference, "explanation": "The census says so.", "pagesRead": 1}
        if reference else None,
        "outcome": outcome,
        "seconds": 2.0,
        "usage": {"calls": 2 if second else 0},
    }

    return record


# ----------------------------------------------------------------------
# The loop
# ----------------------------------------------------------------------


def loop_run(tmp_path):

    return write_run(tmp_path / "run", [
        looped("fact001", "TRUE", "TRUE"),
        # Unverified, fixed by the second look - the trigger fires on it too.
        looped("fact002", "TRUE", "UNVERIFIED", second="TRUE", trigger="unverified", outcome="fixed"),
        # Confidently wrong: the trigger does not fire, the gold label did.
        looped("fact003", "FALSE", "TRUE", second="TRUE", outcome="retrieval", reference="FALSE"),
        looped("fact004", "FALSE", "TRUE", second="TRUE", outcome="adjudicate", reference="TRUE"),
        # Right but unsure: the trigger fires and the second look breaks it.
        looped("fact005", "TRUE", "TRUE", second="FALSE", trigger="low_confidence"),
    ], stem="manual-train")


def test_the_loop_report_sorts_the_disagreements_and_names_who_decides(tmp_path):

    result = loop_report(load_run(loop_run(tmp_path)), **BOOT)

    assert (result["scored"], result["disagreements"]) == (5, 3)
    assert result["outcomes"]["agreed"] == 2
    assert (result["outcomes"]["fixed"], result["outcomes"]["retrieval"], result["outcomes"]["adjudicate"]) == (1, 1, 1)
    assert result["outcomeIds"]["adjudicate"] == ["fact004"]
    assert result["adjudicate"][0]["reference"] == "TRUE"
    assert result["adjudicateVerdicts"] == {"FALSE -> TRUE": 1}

    # First pass: fact001 and fact005 right, 2 of 5.
    assert result["firstPass"]["accuracy"] == 0.4

    # The gold label choosing: fact002 fixed, 3 of 5.
    assert result["goldTriggered"]["accuracy"] == 0.6

    # The trigger alone fires on fact002 (fixed) and fact005 (broken): 2 of 5 still.
    trigger = result["triggers"]["unverifiedOrUnsure"]
    assert (trigger["fired"], trigger["wrongToRight"], trigger["rightToWrong"]) == (2, ["fact002"], ["fact005"])
    assert trigger["comparison"]["accuracy"]["difference"] == 0.0

    # UNVERIFIED only: fact002 alone, 3 of 5.
    unverified = result["triggers"]["unverifiedOnly"]
    assert (unverified["fired"], unverified["rightToWrong"]) == (1, [])
    assert abs(unverified["comparison"]["accuracy"]["difference"] - 0.2) < 1e-9

    assert result["cost"] == {"secondLooks": 4, "referenceChecks": 2, "llmCalls": 8, "seconds": 10.0}


def test_the_loop_report_is_written_beside_the_runs_report(tmp_path):

    target = write_loop_report(loop_run(tmp_path), root=tmp_path / "reports", **BOOT)

    text = (target / "loop.md").read_text(encoding="utf-8")

    assert "For a person to decide" in text and "fact004" in text
    assert (target / "loop.json").exists() and (target / "run.json").exists()
    assert "manual-train" in str(target)
    assert render_loop(loop_report(load_run(loop_run(tmp_path)), **BOOT)) == text


# ----------------------------------------------------------------------
# Consistency
# ----------------------------------------------------------------------


def test_jaccard_of_two_evidence_sets():

    assert jaccard(set(), set()) == 1.0
    assert jaccard({"a", "b"}, {"b", "c"}) == 1 / 3


def test_a_run_compared_with_itself_agrees_entirely(tmp_path):

    records = [
        make_record(custom_row(f"fact00{n}", f"Claim {n}.", label=gold), verdict,
                    evidence=[source(f"https://www.ine.es/{n}")])
        for n, (gold, verdict) in enumerate([("TRUE", "TRUE"), ("TRUE", "FALSE"), ("FALSE", "FALSE")], start=1)
    ]
    a = load_run(write_run(tmp_path / "a", records, key="a" * 12))
    b = load_run(write_run(tmp_path / "b", records, key="b" * 12))

    result = consistency(a, b, **BOOT)

    assert result["verdict"]["agreement"] == 1.0
    assert result["verdict"]["ci"]["agreement"] == {"low": 1.0, "high": 1.0, "undefinedResamples": 0}
    assert result["evidenceOverlap"]["mean"] == 1.0
    assert result["changes"] == []
    assert result["gold"]["comparison"]["difference"] == 0.0


def test_a_change_is_the_models_on_the_same_evidence_and_the_webs_with_other(tmp_path):

    ine, eu, who = (source(url) for url in ("https://www.ine.es/a", "https://eurostat.eu/b", "https://who.int/c"))

    def run(name, verdicts, evidence):
        return load_run(write_run(tmp_path / name, [
            make_record(custom_row(f"fact00{n}", f"Claim {n}.", label="TRUE"), verdict, evidence=items)
            for n, (verdict, items) in enumerate(zip(verdicts, evidence), start=1)
        ], key=name * 12))

    a = run("a", ["TRUE", "TRUE", "TRUE", "TRUE"], [[ine], [ine], [ine, eu], [ine]])
    b = run("b", ["TRUE", "FALSE", "UNVERIFIED", "TRUE"], [[ine], [ine], [who], [ine, eu]])

    result = consistency(a, b, **BOOT)

    # 2 of 4 agree. Run A always TRUE: chance agreement 1 x 2/4 = 0.5, so
    # kappa (0.5 - 0.5) / (1 - 0.5) = 0.
    assert (result["verdict"]["agreement"], result["verdict"]["kappa"]) == (0.5, 0.0)
    assert result["changedOnSameEvidence"] == ["fact002"]
    assert result["changedWithEvidence"] == ["fact003"]
    # Overlaps 1, 1, 0, 1/2: mean 0.625.
    assert result["evidenceOverlap"]["mean"] == 0.625
    assert (result["evidenceOverlap"]["identical"], result["evidenceOverlap"]["disjoint"]) == (2, 1)
    assert (result["gold"]["accuracyA"], result["gold"]["accuracyB"], result["gold"]["onlyA"]) == (1.0, 0.5, 2)

    text = render_consistency(result)
    assert "fact002" in text and "Claims whose verdict changed" in text


def test_only_claims_both_runs_scored_are_compared(tmp_path):

    a = load_run(write_run(tmp_path / "a", [
        make_record(custom_row("fact001", "One.", label="TRUE"), "TRUE"),
        make_record(custom_row("fact002", "Two.", label="TRUE"), "UNVERIFIED", search_unavailable=True),
        make_record(custom_row("fact003", "Three.", label="TRUE"), "TRUE"),
    ], key="a" * 12))
    b = load_run(write_run(tmp_path / "b", [
        make_record(custom_row("fact001", "One.", label="TRUE"), "TRUE"),
        make_record(custom_row("fact002", "Two.", label="TRUE"), "TRUE"),
    ], key="b" * 12, stem="fixture-recheck"))

    result = consistency(a, b, **BOOT)

    assert (result["shared"], result["scored"]) == (2, 1)
    assert result["setApart"] == {"fact002": {"a": "searchUnavailable", "b": "scored"}}
    assert result["onlyA"] == ["fact003"]

    path = write_consistency(a.directory, b.directory, root=tmp_path / "reports", **BOOT)
    assert path.parent == tmp_path / "reports" / "fixture-recheck" / "consistency"


# ----------------------------------------------------------------------
# The pipeline's own second look (a run with second_look_enabled)
# ----------------------------------------------------------------------


def looked(fact_id, gold, final, *, first=None, trigger="unverified"):

    record = make_record(custom_row(fact_id, f"Claim {fact_id}.", label=gold), final)

    if first is not None:
        record["secondLook"] = {
            "trigger": trigger, "first_verdict": first, "first_confidence": 0.0,
            "first_explanation": "", "queries": ["q"], "new_evidence": 1, "search_unavailable": False,
        }

    return record


def test_a_run_that_took_its_own_second_looks_is_read_first_against_final(tmp_path):

    run = write_run(tmp_path / "run", [
        looked("fact001", "TRUE", "TRUE"),
        looked("fact002", "TRUE", "TRUE", first="UNVERIFIED"),
        looked("fact003", "FALSE", "TRUE", first="FALSE", trigger="low_confidence"),
        looked("fact004", "FALSE", "FALSE"),
    ], stem="manual-test")

    target = write_loop_report(run, root=tmp_path / "reports", **BOOT)

    import json
    result = json.loads((target / "loop.json").read_text(encoding="utf-8"))

    # First verdicts TRUE, UNVERIFIED, FALSE, FALSE: 3 of 4.
    assert result["kind"] == "secondLook"
    assert result["firstPass"]["accuracy"] == 0.75
    # Every second look kept: fact002 fixed, fact003 broken, 3 of 4.
    both = result["triggers"]["unverifiedOrUnsure"]
    assert (both["fired"], both["wrongToRight"], both["rightToWrong"]) == (2, ["fact002"], ["fact003"])
    # UNVERIFIED only: fact002 fixed, fact003 keeps its first FALSE, 4 of 4.
    assert result["triggers"]["unverifiedOnly"]["final"]["accuracy"] == 1.0
    assert result["byTrigger"] == {"unverified": 1, "low_confidence": 1}
    assert "as the pipeline takes it" in (target / "loop.md").read_text(encoding="utf-8")


def test_with_second_looks_the_first_passes_are_compared_too(tmp_path):

    def run(name, first_b):
        records = [
            looked("fact001", "TRUE", "TRUE", first="UNVERIFIED"),
            looked("fact002", "TRUE", "FALSE"),
        ]
        if first_b:
            records[0]["secondLook"]["first_verdict"] = first_b
        return load_run(write_run(tmp_path / name, records, key=name * 12))

    result = consistency(run("a", None), run("b", "FALSE"), **BOOT)

    # The final verdicts agree; the first passes did not on fact001.
    assert result["verdict"]["agreement"] == 1.0
    assert result["firstPass"]["agreement"] == 0.5
    assert "before any second look" in render_consistency(result)
