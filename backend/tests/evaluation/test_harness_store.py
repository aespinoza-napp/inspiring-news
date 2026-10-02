"""The append-only results file: what a crash can leave, and what it cannot."""

import json

import pytest

from src.evaluation.store import ResultsFile, ResultsFileError


def test_records_append_one_line_each_and_the_latest_per_key_wins(tmp_path):

    results = ResultsFile(tmp_path / "results.jsonl")

    results.append({"id": "a", "status": "error"})
    results.append({"id": "b", "status": "ok"})
    results.append({"id": "a", "status": "ok"})

    latest = results.latest(lambda record: record["id"])

    assert latest == {"a": {"id": "a", "status": "ok"}, "b": {"id": "b", "status": "ok"}}

    # LF only, on every OS: the loader counts bytes per line.
    assert b"\r\n" not in (tmp_path / "results.jsonl").read_bytes()


def test_a_torn_last_line_is_cut_and_the_next_append_starts_clean(tmp_path):

    path = tmp_path / "results.jsonl"
    path.write_text('{"id": "a"}\n{"id": "b", "sta', encoding="utf-8")

    results = ResultsFile(path)

    assert results.load() == [{"id": "a"}]
    assert results.torn == 1

    results.append({"id": "b"})

    assert [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] == [
        {"id": "a"}, {"id": "b"},
    ]


def test_a_complete_last_record_without_its_newline_is_kept(tmp_path):

    path = tmp_path / "results.jsonl"
    path.write_text('{"id": "a"}', encoding="utf-8")

    results = ResultsFile(path)

    assert results.load() == [{"id": "a"}]
    assert results.torn == 0

    results.append({"id": "b"})

    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_a_damaged_line_that_is_not_the_last_is_refused(tmp_path):

    path = tmp_path / "results.jsonl"
    path.write_text('{"id": "a"}\nnot json\n{"id": "c"}\n', encoding="utf-8")

    with pytest.raises(ResultsFileError, match=":2"):
        ResultsFile(path).load()


def test_set_aside_keeps_the_old_file(tmp_path):

    results = ResultsFile(tmp_path / "results.jsonl")

    assert results.set_aside() is None

    results.append({"id": "a"})

    moved = results.set_aside()

    assert moved.exists() and not (tmp_path / "results.jsonl").exists()
    assert results.load() == []
