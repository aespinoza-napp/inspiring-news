"""
Loading both labelled sets into one row shape.

The committed files are read, never written (invariant 9 is about
data/raw and data/processed; the same courtesy holds here).
"""

import ast
import json
from pathlib import Path

import pytest

from src.config.topics import TOPICS
from src.evaluation.dataset import (
    CUSTOM,
    TOPIC_GROUPS,
    XFACT,
    DatasetError,
    load_dataset,
    xfact_id,
)

from tests.evaluation.support import custom_row, write_jsonl, xfact_row

BACKEND = Path(__file__).resolve().parents[2]
EVALUATION = BACKEND / "data" / "evaluation"
LABELLER = BACKEND.parent / "labeller" / "app.py"


def test_the_committed_pilot_loads_with_64_unique_ids():

    dataset = load_dataset(EVALUATION / "xfact_en_es_pilot.jsonl")

    assert len(dataset.rows) == 64
    assert len({row.id for row in dataset.rows}) == 64
    assert dataset.kinds == [XFACT]
    assert dataset.stem == "xfact_en_es_pilot"
    assert all(row.id.startswith("xf-") and len(row.id) == 15 for row in dataset.rows)

    spanish = [row for row in dataset.rows if row.language == "es"]

    assert spanish and all(row.claim_date is None for row in spanish if row.site == "chequeado.com")


def test_the_custom_set_loads_from_its_directory_before_it_is_joined():

    dataset = load_dataset(EVALUATION / "manual")

    assert dataset.kinds == [CUSTOM]
    assert dataset.stem == "manual"

    first = next(row for row in dataset.rows if row.id == "fact001")

    assert first.language == "es"
    assert first.article_url.startswith("https://")
    assert first.topic_group == "society"
    assert first.claim_date == "2026-09-23"


def test_xfact_ids_are_stable_and_depend_on_language_site_and_claim():

    one = xfact_id("es", "chequeado.com", "Una afirmación")

    assert one == xfact_id("es", "chequeado.com", "Una afirmación")
    assert one != xfact_id("en", "chequeado.com", "Una afirmación")
    assert one != xfact_id("es", "politifact.com", "Una afirmación")


def test_none_claim_dates_and_label_case_are_normalised(tmp_path):

    dataset = load_dataset(write_jsonl(tmp_path / "set.jsonl", [
        xfact_row("A claim.", label="partially_true", claimDate="none"),
    ]))

    row = dataset.rows[0]

    assert row.claim_date is None
    assert row.label == "PARTIALLY_TRUE"
    assert row.dataset == XFACT
    assert row.article_url is None


def test_a_duplicate_is_refused_rather_than_sharing_a_record(tmp_path):

    path = write_jsonl(tmp_path / "set.jsonl", [xfact_row("Same."), xfact_row("Same.")])

    with pytest.raises(DatasetError, match="duplicate"):
        load_dataset(path)


def test_a_label_that_is_not_a_verdict_is_refused(tmp_path):

    path = write_jsonl(tmp_path / "set.jsonl", [xfact_row("A claim.", label="mostly true")])

    with pytest.raises(DatasetError, match="not a Verdict"):
        load_dataset(path)


def test_the_dataset_hash_changes_when_a_label_does(tmp_path):
    """Editing gold after a run starts a new run, not a mixed one."""

    directory = tmp_path / "manual"
    directory.mkdir()

    write_jsonl(directory / "fact001.json", [custom_row("fact001", "Uno.")])

    before = load_dataset(directory).sha256

    write_jsonl(directory / "fact001.json", [custom_row("fact001", "Uno.", label="FALSE")])

    assert load_dataset(directory).sha256 != before


def test_the_topic_groups_match_the_labellers_copy():
    """
    Copied, because the labeller imports nothing from backend/ and backend
    nothing from it. Read with ast, not imported, for the same reason.
    """

    tree = ast.parse(LABELLER.read_text(encoding="utf-8"))

    labeller_groups = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and getattr(node.targets[0], "id", None) == "TOPIC_GROUPS"
    )

    assert TOPIC_GROUPS == labeller_groups


def test_every_topic_belongs_to_exactly_one_group():

    grouped = [topic for topics in TOPIC_GROUPS.values() for topic in topics]

    assert sorted(grouped) == sorted(TOPICS)
    assert len(grouped) == len(set(grouped))


def test_a_crlf_checkout_hashes_like_an_lf_one(tmp_path):
    """
    Git for Windows checks the committed sets out as CRLF: hashed as
    bytes, one set had a different run key per operating system.
    """

    rows = [xfact_row("First claim."), xfact_row("Second claim.", language="es")]

    # Bytes, not write_text: on Windows text mode would already be CRLF.
    lines = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode("utf-8")

    unix = tmp_path / "unix.jsonl"
    unix.write_bytes(lines)

    windows = tmp_path / "windows" / "unix.jsonl"
    windows.parent.mkdir()
    windows.write_bytes(lines.replace(b"\n", b"\r\n"))

    assert load_dataset(windows).sha256 == load_dataset(unix).sha256

    lf_dir, crlf_dir = tmp_path / "lf", tmp_path / "crlf"
    lf_dir.mkdir()
    crlf_dir.mkdir()

    fact = json.dumps(custom_row("fact001", "Uno."), indent=2, ensure_ascii=False)

    (lf_dir / "fact001.json").write_bytes(fact.encode("utf-8"))
    (crlf_dir / "fact001.json").write_bytes(fact.replace("\n", "\r\n").encode("utf-8"))

    assert load_dataset(crlf_dir).sha256 == load_dataset(lf_dir).sha256
