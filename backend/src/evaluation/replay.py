"""
Fixed evidence, for comparing what comes after retrieval.

Two runs of the same pipeline over the same claims differ by their web
search before anything else: the thorough defaults scored 42.0% on the
69 train claims on 2026-10-19 and 50.7% on 2026-10-22, a gap as wide as
any change to the verifier could make. A full run therefore keeps what
retrieval handed the rest of the pipeline for each claim -
`evidence.jsonl`, beside `results.jsonl` - and a replay run (`--replay
<run>`) hands the same candidates to ranking, the model and the scorer
again. Two verifiers replayed over one run differ by their reading alone.

What is kept is `EvidenceRetriever.retrieve`'s whole answer - the
candidates with the page text the scraper read, what it cut and why, the
queries - and the events the retriever said on the way, so a replayed
record has the same queries, candidates and retrieval figures as the run
it replays. Not kept: the claim's embedding, which the ranker computes
again when it is missing (one call to inference/, and the same vector).
"""

import json
import threading
from pathlib import Path

from src.evaluation.record import jsonable
from src.models.fact_checker.evidence import Evidence, RejectedEvidence
from src.services.fact_checker.retrieval.evidence_retriever import RetrievalResult

EVIDENCE = "evidence.jsonl"


def snapshot_entry(result: RetrievalResult, events: list[tuple[str, dict]]) -> dict:
    """One claim's retrieval as `evidence.jsonl` holds it."""

    return {
        "kept": [item.model_dump(mode="json") for item in result.kept],
        "rejected": [item.model_dump(mode="json") for item in result.rejected],
        "queries": list(result.queries),
        "searchUnavailable": result.search_unavailable,
        "events": [{"phase": name, "data": jsonable(data)} for name, data in events],
    }


def load_snapshot(directory: Path) -> dict[str, dict]:
    """
    A run's kept retrievals by claim text, the last for each claim id.
    By text because that is what `retrieve` is handed; the custom set's
    claims are unique within a split.
    """

    path = Path(directory) / EVIDENCE

    if not path.exists():
        raise FileNotFoundError(
            f"{path} does not exist: only a full run made since 2026-10-22 keeps "
            "its evidence, and only that can be replayed."
        )

    # Read only. ResultsFile.load mends a torn last line by truncating
    # the file, which is right for the run that owns it and wrong here:
    # replaying a run still in progress would cut the line it is writing.
    latest: dict[str, dict] = {}

    for line in path.read_bytes().split(b"\n"):

        if not line.strip():
            continue

        try:
            entry = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue

        latest[entry["id"]] = entry

    return {entry["claim"]: entry for entry in latest.values()}


class RecordingRetriever:
    """
    The real retriever, its first answer for the claim in flight kept.

    Per thread, because the harness checks several claims at once and
    each claim's retrieval runs on the thread that checks it. `begin`
    before the claim, `taken` after: only the first retrieval counts,
    so a second look's wider search never replaces the pass it widened.
    """

    def __init__(self, retriever):

        self._retriever = retriever
        self._local = threading.local()

    def __getattr__(self, name):

        # The scraper and the search provider, which the second look and
        # a check against given pages reach through the retriever.
        return getattr(self._retriever, name)

    def begin(self) -> None:

        self._local.taken = None

    def taken(self) -> dict | None:

        return getattr(self._local, "taken", None)

    def retrieve(self, claim, thresholds=None, context=None, language=None, on_phase=None, deadline=None):

        events: list[tuple[str, dict]] = []

        def forward(name: str, data: dict) -> None:

            events.append((name, data))

            if on_phase is not None:
                on_phase(name, data)

        result = self._retriever.retrieve(
            claim,
            thresholds,
            context=context,
            language=language,
            on_phase=forward,
            deadline=deadline,
        )

        if self.taken() is None:
            self._local.taken = snapshot_entry(result, events)

        return result


class ReplayRetriever:
    """
    Answers `retrieve` from a kept snapshot instead of the web: the same
    candidates, the same events said again in order. A claim the snapshot
    does not have is an error record, never a search - a replay that
    quietly searched would compare two retrievals again.
    """

    def __init__(self, entries: dict[str, dict], retriever=None):

        self._entries = entries
        self._retriever = retriever

    def __getattr__(self, name):

        if self._retriever is None:
            raise AttributeError(name)

        return getattr(self._retriever, name)

    def retrieve(self, claim, thresholds=None, context=None, language=None, on_phase=None, deadline=None):

        entry = self._entries.get(claim.text)

        if entry is None:
            raise KeyError(f"claim not in the replayed run's evidence: {claim.text[:80]!r}")

        if on_phase is not None:
            for event in entry.get("events") or []:
                on_phase(event["phase"], dict(event["data"]))

        return RetrievalResult(
            kept=[Evidence.model_validate(item) for item in entry.get("kept") or []],
            rejected=[RejectedEvidence.model_validate(item) for item in entry.get("rejected") or []],
            queries=list(entry.get("queries") or []),
            claim_embedding=None,
            search_unavailable=bool(entry.get("searchUnavailable")),
        )
