import ast
import json
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr

import src.services.evaluation_summary as summary_module
from src.config.settings import settings
from src.main import app
from src.services.evaluation_summary import (
    AI_NOTE_PREFIX,
    LABELS,
    SKIP_REASONS,
    TOPIC_GROUPS,
    evaluation_summary,
)

LABELLER = Path(__file__).resolve().parents[3] / "labeller" / "app.py"


def fact(number: int, label="TRUE", topic="space", note=None, **extra) -> dict:
    return {
        "language": "en",
        "site": "esa.int",
        "claimant": "ESA",
        "claim": f"Claim {number}.",
        "claimDate": "2026-09-30",
        "reviewDate": "2026-10-02T10:00:00",
        "labelRaw": "supported",
        "label": label,
        "referenceEvidenceLinks": ["https://example.org/a"],
        "split": "test",
        "id": f"fact{number:03d}",
        "topic": topic,
        "claimType": "factual",
        "sourceTier": "primary",
        "onlyOwnSource": False,
        "evidenceDate": "2026-09-01",
        "articleUrl": "https://esa.int/x",
        "annotatorNote": note,
        "createdAt": "2026-10-02T10:00:00",
        "review": None,
        **extra,
    }


def write_facts(base: Path, *facts: dict) -> None:
    folder = base / "manual"
    folder.mkdir(parents=True, exist_ok=True)
    for f in facts:
        (folder / f"{f['id']}.json").write_text(json.dumps(f), encoding="utf-8")


def write_batch(base: Path, name: str, statuses: list[tuple[str, str, str | None]]) -> None:
    """statuses: (language, status, skipReason) per claim, one article each."""

    folder = base / "queue"
    folder.mkdir(parents=True, exist_ok=True)
    articles = [
        {"language": language, "claims": [{"status": status, "skipReason": reason}]}
        for language, status, reason in statuses
    ]
    (folder / name).write_text(
        json.dumps({"date": name[:10], "articles": articles}), encoding="utf-8"
    )


# ---------------------------------------------------------------------
# The labelled facts
# ---------------------------------------------------------------------


def test_nothing_on_disk_is_an_empty_answer_not_an_error(tmp_path):

    result = evaluation_summary(tmp_path)

    assert result["found"] is False
    assert result["facts"] == []
    assert result["totals"]["total"] == 0
    assert result["selection"]["precision"] is None
    assert result["runs"] == []


def test_facts_are_counted_per_verdict_group_and_cell(tmp_path):

    write_facts(
        tmp_path,
        fact(1, "TRUE", "space"),
        fact(2, "TRUE", "climate"),
        fact(3, "FALSE", "space"),
        fact(4, "UNVERIFIED", "medicine"),
    )

    totals = evaluation_summary(tmp_path)["totals"]

    assert totals["total"] == 4
    assert totals["byLabel"] == {
        "TRUE": 2, "PARTIALLY_TRUE": 0, "MISLEADING": 0, "FALSE": 1, "UNVERIFIED": 1,
    }
    assert totals["byGroup"]["science"] == 2
    assert totals["matrix"]["TRUE"]["environment"] == 1
    assert totals["matrix"]["FALSE"]["science"] == 1
    # 150 facts over 5 verdicts x 5 groups.
    assert totals["perCell"] == 6


def test_facts_come_back_in_number_order_not_name_order(tmp_path):

    write_facts(tmp_path, fact(100), fact(9), fact(10))

    ids = [f["id"] for f in evaluation_summary(tmp_path)["facts"]]

    assert ids == ["fact009", "fact010", "fact100"]


def test_a_fact_labelled_by_an_ai_is_told_apart_from_a_human_one(tmp_path):
    """The paper's method is one human annotator: AI labels are shown apart."""

    write_facts(
        tmp_path,
        fact(1, note="Checked the report."),
        fact(2, note=f"{AI_NOTE_PREFIX} Claude, 2026-10-02] NSIDC says so."),
    )

    result = evaluation_summary(tmp_path)

    assert [f["annotator"] for f in result["facts"]] == ["human", "ai"]
    assert result["totals"]["byAnnotator"] == {"human": 1, "ai": 1}


def test_a_broken_fact_file_is_reported_and_the_rest_still_read(tmp_path):

    write_facts(tmp_path, fact(1))
    (tmp_path / "manual" / "fact002.json").write_text("{not json", encoding="utf-8")

    result = evaluation_summary(tmp_path)

    assert [f["id"] for f in result["facts"]] == ["fact001"]
    assert result["brokenFacts"][0]["file"] == "fact002.json"


def test_an_undeclared_label_is_counted_rather_than_dropped(tmp_path):

    write_facts(tmp_path, fact(1, label="MOSTLY_TRUE"))

    assert evaluation_summary(tmp_path)["totals"]["byLabel"]["MOSTLY_TRUE"] == 1


def test_labelling_is_counted_per_day(tmp_path):

    write_facts(
        tmp_path,
        fact(1, createdAt="2026-09-30T08:00:00"),
        fact(2, createdAt="2026-10-01T08:00:00"),
        fact(3, createdAt="2026-10-01T09:00:00"),
    )

    assert evaluation_summary(tmp_path)["totals"]["perDay"] == [
        {"date": "2026-09-30", "value": 1},
        {"date": "2026-10-01", "value": 2},
    ]


# ---------------------------------------------------------------------
# The claim selector's precision
# ---------------------------------------------------------------------


def test_selection_precision_is_labelled_over_labelled_plus_skipped(tmp_path):
    """Pending proposals have not been judged, so they are not in it."""

    write_batch(tmp_path, "2026-10-01.json", [
        ("en", "labelled", None),
        ("en", "skipped", "opinion"),
        ("es", "labelled", None),
        ("es", "pending", None),
    ])
    write_batch(tmp_path, "2026-10-02.json", [("en", "skipped", "fragment")])

    selection = evaluation_summary(tmp_path)["selection"]

    assert selection["proposed"] == 5
    assert (selection["labelled"], selection["skipped"], selection["pending"]) == (2, 2, 1)
    assert selection["precision"] == 0.5
    assert selection["byReason"]["opinion"] == 1
    assert selection["byReason"]["fragment"] == 1
    assert selection["byLanguage"]["es"]["precision"] == 1.0
    assert [b["date"] for b in selection["batches"]] == ["2026-10-01", "2026-10-02"]


# ---------------------------------------------------------------------
# The harness's reports
# ---------------------------------------------------------------------


def test_a_harness_report_is_passed_through_with_its_run(tmp_path):

    key = tmp_path / "reports" / "xfact_en_es_pilot" / "llama3.2-3b" / "abc123"
    key.mkdir(parents=True)
    (key / "metrics.json").write_text(json.dumps({"accuracy": 0.5}), encoding="utf-8")
    (key / "run.json").write_text(json.dumps({"model": "llama3.2:3b"}), encoding="utf-8")

    runs = evaluation_summary(tmp_path)["runs"]

    assert runs == [{
        "dataset": "xfact_en_es_pilot",
        "model": "llama3.2-3b",
        "key": "abc123",
        "modifiedAt": runs[0]["modifiedAt"],
        "metrics": {"accuracy": 0.5},
        "run": {"model": "llama3.2:3b"},
        "error": None,
    }]


def test_an_oversized_report_is_refused_not_shipped(tmp_path, monkeypatch):

    monkeypatch.setattr(summary_module, "MAX_REPORT_BYTES", 10)
    key = tmp_path / "reports" / "d" / "m" / "k"
    key.mkdir(parents=True)
    (key / "metrics.json").write_text(json.dumps({"accuracy": 0.123456789}), encoding="utf-8")

    run = evaluation_summary(tmp_path)["runs"][0]

    assert run["metrics"] is None
    assert "over 10" in run["error"]


# ---------------------------------------------------------------------
# Held to the labeller, which this module may not import
# ---------------------------------------------------------------------


def _labeller_constant(name: str):
    tree = ast.parse(LABELLER.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {LABELLER}")


def test_topic_groups_match_the_labellers():
    assert TOPIC_GROUPS == _labeller_constant("TOPIC_GROUPS")


def test_labels_and_skip_reasons_match_the_labellers():
    assert list(LABELS) == list(_labeller_constant("LABELS"))
    assert list(SKIP_REASONS) == list(_labeller_constant("SKIP_REASONS"))


# ---------------------------------------------------------------------
# The route
# ---------------------------------------------------------------------


def test_the_route_reads_the_evaluation_folder_behind_the_storage_key(tmp_path, monkeypatch):

    write_facts(tmp_path, fact(1))
    monkeypatch.setattr(summary_module, "EVALUATION_PATH", tmp_path)
    monkeypatch.setattr(settings, "STORAGE_API_KEY", SecretStr("secret"))
    client = TestClient(app)

    assert client.get("/evaluation/summary").status_code == 401

    response = client.get("/evaluation/summary", headers={"x-api-key": "secret"})

    assert response.status_code == 200
    assert response.json()["totals"]["total"] == 1
