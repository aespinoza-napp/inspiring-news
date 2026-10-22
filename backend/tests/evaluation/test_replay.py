"""
A full run keeps what retrieval found for each claim; a replay run hands
it to ranking, the model and the scorer again, without searching.

src/evaluation/replay.py; docs/decisions/evaluation.md §Replay.
"""

import json

from src.evaluation.dataset import load_dataset
from src.evaluation.replay import EVIDENCE, RecordingRetriever, ReplayRetriever, load_snapshot
from src.evaluation.runner import HarnessRunner, RunConfig, latest_records
from src.models.core.claim import Claim

from tests.evaluation.support import (
    claim_service,
    custom_row,
    full_checker,
    open_gate,
    stub_llm,
    write_jsonl,
)


def two_rows(tmp_path):

    return load_dataset(write_jsonl(tmp_path / "set.jsonl", [
        custom_row("fact001", "Uno de cada tres niños en España vive en riesgo de pobreza."),
        custom_row("fact002", "El paro bajó al 10% en 2026."),
    ]))


def answer(verdict: str) -> dict:

    return {
        "verdict": verdict, "confidence": 0.8, "explanation": "x", "cited_evidence": [0],
        "assessments": [{"index": 0, "stance": "supports" if verdict == "TRUE" else "contradicts", "quote": ""}],
    }


def runner(dataset, checker, tmp_path, *, mode="full", replay_of=None, recorder=None) -> HarnessRunner:

    config = RunConfig(
        dataset=dataset,
        model="stub-model",
        thresholds=open_gate(),
        corpus="none",
        root=tmp_path / "runs",
        mode=mode,
        replay_of=replay_of,
    )

    return HarnessRunner(
        config,
        checker=checker,
        claims=claim_service(checker),
        provider="localhost:11434",
        commit="abc123",
        max_workers=1,
        recorder=recorder,
    )


def searched_run(repository, tmp_path, dataset):

    checker = full_checker(repository, stub_llm(answer("TRUE")))
    recorder = RecordingRetriever(checker.evidence_retriever)
    checker.evidence_retriever = recorder

    first = runner(dataset, checker, tmp_path, recorder=recorder)
    first.run()

    return first, checker


class _NoSearch:
    """The real retriever's stand-in in a replay: any search fails the test."""

    def retrieve(self, *args, **kwargs):
        raise AssertionError("a replay searched")


def test_a_full_run_keeps_each_claims_candidates_with_their_text(repository, tmp_path):

    dataset = two_rows(tmp_path)

    first, _ = searched_run(repository, tmp_path, dataset)

    entries = [json.loads(line) for line in (first.directory / EVIDENCE).read_text(encoding="utf-8").splitlines()]

    assert [entry["id"] for entry in entries] == ["fact001", "fact002"]

    entry = entries[0]

    assert entry["claim"] == dataset.rows[0].claim
    assert entry["kept"], "the candidates retrieval handed on"
    # The page text the model reads is what a replay must not fetch again.
    assert any(item.get("content") for item in entry["kept"])
    assert [event["phase"] for event in entry["events"]][:1] == ["searching_web"]


def test_a_replay_judges_the_same_candidates_without_searching(repository, tmp_path):

    dataset = two_rows(tmp_path)

    first, _ = searched_run(repository, tmp_path, dataset)

    # Another verifier over the same candidates: here, one that says FALSE.
    checker = full_checker(repository, stub_llm(answer("FALSE")))
    checker.evidence_retriever = ReplayRetriever(load_snapshot(first.directory), _NoSearch())

    second = runner(dataset, checker, tmp_path, mode="replay", replay_of=first.directory)
    session = second.run()

    assert session["ok"] == 2

    before = latest_records(first.directory)
    after = latest_records(second.directory)

    for fact_id in ("fact001", "fact002"):
        # Same queries, same sources: the retrieval figures of the report
        # are the replayed run's.
        assert after[fact_id]["queries"] == before[fact_id]["queries"]
        assert [c["url"] for c in after[fact_id]["candidates"]] == [c["url"] for c in before[fact_id]["candidates"]]
        assert before[fact_id]["rawVerdict"] == "TRUE"
        assert after[fact_id]["rawVerdict"] == "FALSE"

    # A replay keeps nothing of its own to replay.
    assert not (second.directory / EVIDENCE).exists()


def test_a_replay_is_its_own_run_one_per_run_replayed(repository, tmp_path):

    dataset = two_rows(tmp_path)

    first, _ = searched_run(repository, tmp_path, dataset)

    def key(replay_of):
        return RunConfig(
            dataset=dataset, model="stub-model", thresholds=open_gate(), corpus="none",
            root=tmp_path / "runs", mode="replay", replay_of=replay_of,
        ).key

    assert key(first.directory) != first.config.key
    assert key(first.directory) != key(tmp_path / "another-run")
    assert key(first.directory) == key(tmp_path / "elsewhere" / first.directory.name)


def test_a_claim_the_replayed_run_never_searched_is_an_error_not_a_search(repository, tmp_path):

    dataset = two_rows(tmp_path)

    first, _ = searched_run(repository, tmp_path, dataset)

    snapshot = load_snapshot(first.directory)
    snapshot.pop(dataset.rows[1].claim)

    checker = full_checker(repository, stub_llm(answer("TRUE")))
    checker.evidence_retriever = ReplayRetriever(snapshot, _NoSearch())

    second = runner(dataset, checker, tmp_path, mode="replay", replay_of=first.directory)
    session = second.run()

    assert session["ok"] == 1
    assert session["errors"] == 1
    assert "not in the replayed run" in latest_records(second.directory)["fact002"]["error"]


def test_only_a_claims_first_retrieval_is_kept(repository):

    checker = full_checker(repository, stub_llm(answer("TRUE")))
    recorder = RecordingRetriever(checker.evidence_retriever)

    claim = Claim(text="El paro bajó al 10% en 2026.", entities={}, confidence=1.0)

    recorder.begin()
    first = recorder.retrieve(claim, open_gate())
    kept = recorder.taken()

    # A second look's wider search, on the same thread, for the same claim.
    recorder.retrieve(Claim(text="otra búsqueda", entities={}, confidence=1.0), open_gate())

    assert recorder.taken() is kept
    assert [item["url"] for item in kept["kept"]] == [item.url for item in first.kept]


def test_reading_a_run_in_progress_never_cuts_its_file(repository, tmp_path):

    dataset = two_rows(tmp_path)

    first, _ = searched_run(repository, tmp_path, dataset)

    path = first.directory / EVIDENCE

    # The run is writing its next line, half of it on disk.
    with path.open("ab") as handle:
        handle.write(b'{"id": "fact003", "claim": "half a li')

    before = path.read_bytes()

    snapshot = load_snapshot(first.directory)

    assert path.read_bytes() == before
    assert sorted(entry["id"] for entry in snapshot.values()) == ["fact001", "fact002"]
