"""
The harness's run loop: what it hands the pipeline, what it writes, and
that a run interrupted at any point resumes without paying again for a
claim it already has.

docs/decisions/evaluation.md §How one claim is run, §Record format,
§Run layout, cache and resume.
"""

import json

import pytest

from src.config.thresholds import PipelineThresholds
from src.evaluation.dataset import load_dataset
from src.evaluation.record import HARNESS_VERSION, RECORD_FIELDS
from src.evaluation.runner import (
    RESULTS,
    HarnessRunner,
    RunConfig,
    is_done,
    latest_records,
    model_slug,
    prepare_corpus,
    provider_of,
)
from src.evaluation.usage import UsageMeter, metered
from src.models.fact_checker.fact_check import FactCheck, Verdict

from tests.evaluation.support import (
    claim_service,
    custom_row,
    full_checker,
    open_gate,
    recording_checker,
    stub_llm,
    write_jsonl,
    xfact_row,
)


def five_rows(tmp_path):

    return load_dataset(write_jsonl(tmp_path / "set.jsonl", [
        xfact_row(f"Claim number {n} about the world.") for n in range(1, 6)
    ]))


def runner_for(dataset, checker, tmp_path, **kwargs) -> HarnessRunner:

    config = RunConfig(
        dataset=dataset,
        model=kwargs.pop("model", "stub-model"),
        thresholds=kwargs.pop("thresholds", PipelineThresholds()),
        corpus="none",
        root=tmp_path / "runs",
        loop=kwargs.pop("loop", False),
        mode=kwargs.pop("mode", "full"),
    )

    return HarnessRunner(
        config,
        checker=checker,
        claims=claim_service(checker),
        provider="localhost:11434",
        commit="abc123",
        max_workers=kwargs.pop("max_workers", 1),
        **kwargs,
    )


def checked_claims(retriever) -> list[str]:

    return [claim.text for claim, *_ in retriever.calls]


def lines(runner: HarnessRunner) -> list[str]:

    return (runner.directory / RESULTS).read_text(encoding="utf-8").splitlines()


# ----------------------------------------------------------------------
# The five things G2 has to prove
# ----------------------------------------------------------------------


def test_a_run_killed_after_claim_k_resumes_without_rechecking_claims_1_to_k(repository, tmp_path):
    """(1) A crash at claim 90 must not re-pay claims 1-89."""

    dataset = five_rows(tmp_path)

    checker, retriever = recording_checker(repository)

    first = runner_for(dataset, checker, tmp_path)

    # Killed after the second claim was written: nothing after it starts.
    first.on_record = lambda record: (
        first.stop() if len(lines(first)) == 2 else None
    )

    session = first.run()

    assert session["ok"] == 2
    assert session["stopped"] is True
    assert checked_claims(retriever) == [row.claim for row in dataset.rows[:2]]

    checker, retriever = recording_checker(repository)

    second = runner_for(dataset, checker, tmp_path)

    session = second.run()

    assert checked_claims(retriever) == [row.claim for row in dataset.rows[2:]]
    assert session["ok"] == 3

    records = latest_records(second.directory)

    assert sorted(records) == sorted(row.id for row in dataset.rows)
    assert all(record["status"] == "ok" for record in records.values())

    # Two sessions in one manifest, the first one's provenance kept.
    manifest = json.loads((second.directory / "run.json").read_text(encoding="utf-8"))
    assert [s["ok"] for s in manifest["sessions"]] == [2, 3]


def test_a_torn_last_line_is_rerun_and_cut_from_the_file(repository, tmp_path):
    """(2) A crash mid-write leaves half a line; that claim is not done."""

    dataset = five_rows(tmp_path)

    checker, _ = recording_checker(repository)

    runner = runner_for(dataset, checker, tmp_path)
    runner.run(limit=3)

    results = runner.directory / RESULTS
    data = results.read_bytes()

    # Cut the third record in half, newline and all.
    results.write_bytes(data[: len(data) - 60])

    checker, retriever = recording_checker(repository)

    resumed = runner_for(dataset, checker, tmp_path)
    session = resumed.run(limit=3)

    assert checked_claims(retriever) == [dataset.rows[2].claim]
    assert session["tornLinesDropped"] == 1

    # Three whole lines: the fragment was cut, not glued to.
    assert [json.loads(line)["id"] for line in lines(resumed)] == [
        row.id for row in dataset.rows[:3]
    ]


def test_spanish_rows_reach_check_claim_with_their_language(repository, tmp_path):
    """
    (3) Without it the query builder fell back to English, and the 40
    Spanish pilot claims would have been searched with the English
    lexicon.
    """

    dataset = load_dataset(write_jsonl(tmp_path / "set.jsonl", [
        xfact_row("La inflación bajó al 3% en 2024.", language="es", site="chequeado.com"),
        xfact_row("Inflation fell to 3% in 2024.", language="en"),
    ]))

    checker, retriever = recording_checker(repository)

    runner_for(dataset, checker, tmp_path).run()

    languages = {claim.text: language for claim, _, _, language in retriever.calls}

    assert languages == {
        "La inflación bajó al 3% en 2024.": "es",
        "Inflation fell to 3% in 2024.": "en",
    }


def test_custom_rows_pass_their_article_as_context_and_xfact_rows_pass_none(repository, tmp_path):
    """
    (4) A custom-set claim must not be "confirmed" by the article it came
    from; x-fact gets nothing from the gold row that production would not
    have.
    """

    dataset = load_dataset(write_jsonl(tmp_path / "set.jsonl", [
        custom_row("fact001", "Un parque solar abastece a 1.200 hogares.",
                   articleUrl="https://lacarabuenadelmundo.com/parque-solar/"),
        xfact_row("A solar park powers 1,200 homes."),
    ]))

    checker, retriever = recording_checker(repository)

    runner_for(dataset, checker, tmp_path).run()

    contexts = {claim.text: context for claim, _, context, _ in retriever.calls}

    custom = contexts["Un parque solar abastece a 1.200 hogares."]

    assert custom.url == "https://lacarabuenadelmundo.com/parque-solar/"
    assert (custom.title, custom.lead, custom.keywords, custom.entities) == ("", "", [], {})

    assert contexts["A solar park powers 1,200 homes."] is None


def test_every_field_of_the_record_format_is_filled(repository, tmp_path):
    """
    (5) The real retriever, ranker, verifier and scorer over the shared
    fakes, and a real LLMClient over a stubbed SDK: a record a report can
    read without asking whether a key exists.
    """

    dataset = load_dataset(write_jsonl(tmp_path / "set.jsonl", [
        custom_row("fact001", "Uno de cada tres niños en España vive en riesgo de pobreza.",
                   label="MISLEADING", labelRaw="conflicting evidence/cherrypicking"),
    ]))

    meter = UsageMeter()

    llm = metered(stub_llm({
        "verdict": "MISLEADING",
        "confidence": 0.7,
        "explanation": "The figure includes social exclusion.",
        "cited_evidence": [0, 1],
        "assessments": [
            # FakeEvidenceScraper replaces the body; the title is still
            # part of what a quote is checked against.
            {"index": 0, "stance": "contradicts",
             "quote": "Encuesta de condiciones de vida 2025"},
            {"index": 1, "stance": "supports"},
        ],
    }, usage=(900, 120)), meter)

    checker = full_checker(repository, llm)

    runner = runner_for(dataset, checker, tmp_path, meter=meter, thresholds=open_gate())
    runner.run()

    record = json.loads(lines(runner)[0])

    assert list(record) == list(RECORD_FIELDS)

    # Null only where null is the pipeline's real answer: no error, no
    # stage note for a verdict that was not recalibrated, no second look
    # in a run that did not enable one, and no loop in a run without it.
    nullable = {"error", "stageNote", "secondLook", "loop"}

    empty = [
        key for key, value in record.items()
        if key not in nullable and (value is None or value == [] or value == {})
    ]

    assert empty == []

    assert record["status"] == "ok"
    assert record["rawVerdict"] == "MISLEADING"
    assert record["topicGroup"] == "environment"
    assert record["queries"] == [
        {"text": "query for Uno de cada tres niños en España vive en riesgo de pobreza.",
         "kind": "anchor"},
    ]

    assert [item["stoppedAt"] for item in record["candidates"]] == ["ranked", "ranked"]

    first = record["evidence"][0]

    assert set(first) == {
        "url", "domain", "title", "origin", "publishedAt", "relevance", "semantic",
        "lexical", "recency", "reliability", "reliabilityKnown", "pertinence",
        "stance", "cited", "quote", "engines", "foundBy",
    }
    assert first["stance"] == "contradicts"
    assert first["quote"] == "Encuesta de condiciones de vida 2025"
    assert first["cited"] is True
    assert "content" not in first

    phases = [event["phase"] for event in record["events"]]

    assert phases[0] == "extracting_entities"
    assert phases[-1] == "claim_checked"

    latency = record["latency"]

    assert all(latency[span] is not None for span in ("total", "entities", "retrieval", "ranking", "llm"))

    assert record["usage"]["calls"] == 1
    assert record["usage"]["promptTokens"] == 900
    assert record["usage"]["completionTokens"] == 120

    assert record["harnessVersion"] == HARNESS_VERSION
    assert record["provider"] == "localhost:11434"
    assert record["gitCommit"] == "abc123"


# ----------------------------------------------------------------------
# Resume rules
# ----------------------------------------------------------------------


def test_an_error_is_written_and_retried_on_the_next_run(repository, tmp_path):

    dataset = five_rows(tmp_path)

    checker, _ = recording_checker(repository)

    def explode(*args, **kwargs):
        raise RuntimeError("inference down")

    runner = runner_for(dataset, checker, tmp_path)
    runner.claims.build_claim = explode

    session = runner.run(limit=1)

    assert session["errors"] == 1

    record = latest_records(runner.directory)[dataset.rows[0].id]

    assert record["status"] == "error"
    assert record["error"] == "RuntimeError: inference down"
    assert list(record) == list(RECORD_FIELDS)

    checker, retriever = recording_checker(repository)

    runner_for(dataset, checker, tmp_path).run(limit=1)

    assert checked_claims(retriever) == [dataset.rows[0].claim]
    assert latest_records(runner.directory)[dataset.rows[0].id]["status"] == "ok"


def test_retry_unavailable_reruns_claims_whose_search_never_answered(repository, tmp_path):

    dataset = five_rows(tmp_path)

    checker, retriever = recording_checker(repository)
    retriever.search_unavailable = True

    runner_for(dataset, checker, tmp_path).run(limit=2)

    checker, retriever = recording_checker(repository)

    runner_for(dataset, checker, tmp_path).run(limit=2)

    assert checked_claims(retriever) == []

    runner_for(dataset, checker, tmp_path).run(limit=2, retry_unavailable=True)

    assert checked_claims(retriever) == [row.claim for row in dataset.rows[:2]]


def test_fresh_sets_the_old_results_aside_and_starts_over(repository, tmp_path):

    dataset = five_rows(tmp_path)

    checker, _ = recording_checker(repository)

    runner = runner_for(dataset, checker, tmp_path)
    runner.run(limit=2)

    checker, retriever = recording_checker(repository)

    session = runner_for(dataset, checker, tmp_path).run(limit=2, fresh=True)

    assert checked_claims(retriever) == [row.claim for row in dataset.rows[:2]]
    assert session["setAside"] is not None
    assert len(list(runner.directory.glob("results.replaced-*.jsonl"))) == 1


def test_is_done_counts_ok_and_retries_the_rest():

    assert is_done({"status": "ok"}) is True
    assert is_done({"status": "error"}) is False
    assert is_done(None) is False
    assert is_done({"status": "ok", "llmUnreachable": True}) is True
    assert is_done({"status": "ok", "llmUnreachable": True}, retry_unavailable=True) is False


# ----------------------------------------------------------------------
# Keys and layout
# ----------------------------------------------------------------------


def test_the_run_key_changes_with_what_changes_the_results(tmp_path):

    dataset = five_rows(tmp_path)

    base = RunConfig(dataset=dataset, model="a", corpus="none", root=tmp_path)

    same = RunConfig(dataset=dataset, model="a", corpus="none", root=tmp_path)

    assert base.key == same.key

    others = [
        RunConfig(dataset=dataset, model="b", corpus="none", root=tmp_path),
        RunConfig(dataset=dataset, model="a", corpus="snapshot", root=tmp_path),
        RunConfig(
            dataset=dataset, model="a", corpus="none", root=tmp_path,
            thresholds=PipelineThresholds(evidence_min_pertinence=0.5),
        ),
        # Environment-only, read once at import: a weight changed for the
        # tuning phase is a different run, not a resumable one.
        RunConfig(
            dataset=dataset, model="a", corpus="none", root=tmp_path,
            weights={**base.weights, "CONFIDENCE_LLM_WEIGHT": 0.6, "CONFIDENCE_EVIDENCE_WEIGHT": 0.4},
        ),
    ]

    assert len({base.key, *(config.key for config in others)}) == 5

    assert base.directory == tmp_path / "set" / "a" / base.key


def test_a_model_name_becomes_a_directory_name_and_a_url_a_provider():

    assert model_slug("llama3.2:3b") == "llama3.2-3b"
    assert model_slug("meta-llama/llama-4-scout") == "meta-llama-llama-4-scout"

    assert provider_of("http://localhost:11434/v1") == "localhost:11434"
    assert provider_of("https://api.groq.com/openai/v1") == "api.groq.com"


def test_the_snapshot_copies_the_corpus_without_the_live_lock(tmp_path):

    live = tmp_path / "vector_db"
    (live / "collection" / "news").mkdir(parents=True)
    (live / "collection" / "news" / "storage.sqlite").write_bytes(b"points")
    (live / ".lock").write_text("held by the backend")

    target = prepare_corpus(tmp_path / "run", "snapshot", source=live)

    assert (target / "collection" / "news" / "storage.sqlite").read_bytes() == b"points"
    assert not (target / ".lock").exists()

    # A resumed run keeps the copy it started with.
    (live / "collection" / "news" / "storage.sqlite").write_bytes(b"grown since")

    assert prepare_corpus(tmp_path / "run", "snapshot", source=live) == target
    assert (target / "collection" / "news" / "storage.sqlite").read_bytes() == b"points"


def test_corpus_none_is_an_empty_store(tmp_path):

    live = tmp_path / "vector_db"
    live.mkdir()
    (live / "data").write_text("x")

    target = prepare_corpus(tmp_path / "run", "none", source=live)

    assert list(target.iterdir()) == []

    with pytest.raises(ValueError):
        prepare_corpus(tmp_path / "other", "live")


def test_check_claim_answers_are_recorded_as_values_not_enums(repository, tmp_path):
    """Verdicts are str enums; the file must hold "TRUE", not "Verdict.TRUE"."""

    dataset = five_rows(tmp_path)

    class Canned:

        def check_claim(self, claim, on_phase=None, thresholds=None, *, context=None, language=None):
            return FactCheck(
                verdict=Verdict.TRUE,
                raw_verdict=Verdict.TRUE,
                explanation="ok",
                confidence=0.9,
                claim=claim.text,
            )

    checker, _ = recording_checker(repository)

    runner = runner_for(dataset, checker, tmp_path)
    runner.checker = Canned()
    runner.run(limit=1)

    raw = lines(runner)[0]

    assert '"verdict": "TRUE"' in raw
    assert '"reachedStage": "aggregation"' in raw


def test_each_session_records_the_environment_it_ran_in(repository, tmp_path, monkeypatch):
    """
    Found by the pilot (2026-10-13): inference timed out under four
    concurrent claims, and the run was resumed with a longer timeout and
    fewer claims at once. Neither is keyed, and only the manifest held
    them, written once by the first session: the record would have said
    the whole run used the first session's values.
    """

    from src.config.settings import settings

    dataset = five_rows(tmp_path)

    checker, _ = recording_checker(repository)
    first = runner_for(dataset, checker, tmp_path, max_workers=4)
    first.on_record = lambda record: first.stop() if len(lines(first)) == 2 else None
    first.run()

    monkeypatch.setattr(settings, "INFERENCE_TIMEOUT", 120.0)

    checker, _ = recording_checker(repository)
    runner_for(dataset, checker, tmp_path, max_workers=2).run()

    manifest = json.loads((first.directory / "run.json").read_text(encoding="utf-8"))

    sessions = [session["settings"] for session in manifest["sessions"]]

    assert [s["CLAIM_MAX_CONCURRENCY"] for s in sessions] == [4, 2]
    assert sessions[1]["INFERENCE_TIMEOUT"] == 120.0
    assert sessions[0]["INFERENCE_TIMEOUT"] != 120.0

    # The manifest's own copy stays the first session's: it is the run's
    # provenance, the sessions say how it was resumed.
    assert manifest["settings"] == sessions[0]


def test_each_session_records_what_it_cost(repository, tmp_path):
    """Summed per session in run.json, so each resume says what it paid."""

    dataset = load_dataset(write_jsonl(tmp_path / "set.jsonl", [
        custom_row("fact001", "Uno de cada tres niños en España vive en riesgo de pobreza."),
    ]))

    meter = UsageMeter()

    llm = metered(stub_llm({
        "verdict": "TRUE", "confidence": 0.7, "explanation": "x", "cited_evidence": [0],
    }, usage=(900, 120)), meter)

    runner = runner_for(dataset, full_checker(repository, llm), tmp_path, meter=meter, thresholds=open_gate())

    session = runner.run()

    assert session["usage"]["llmCalls"] == 1
    assert session["usage"]["promptTokens"] == 900
    assert session["usage"]["completionTokens"] == 120

    manifest = json.loads((runner.directory / "run.json").read_text(encoding="utf-8"))

    assert manifest["sessions"][-1]["usage"]["promptTokens"] == 900


def test_a_slow_dirty_check_keeps_the_commit(monkeypatch):
    """
    Found by the pilot (2026-10-13): over compose's bind mount `git
    status` took 5.0-5.3 s against a 5 s timeout, and a session recorded
    `gitCommit: unknown` although `rev-parse` had answered at once. HEAD
    is kept, marked as unverified, and the timeout no longer sits on the
    measured time.
    """

    import subprocess

    from src.evaluation import runner

    calls = []

    def fake_run(command, **kwargs):
        calls.append((command[1], kwargs.get("timeout")))
        if command[1] == "status":
            raise subprocess.TimeoutExpired(command, kwargs.get("timeout"))
        return subprocess.CompletedProcess(command, 0, stdout="abc123\n", stderr="")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    assert runner.git_commit() == "abc123-unchecked"
    assert dict(calls)["status"] >= 30


def test_no_repository_is_still_unknown_and_a_dirty_tree_says_so(monkeypatch):

    import subprocess

    from src.evaluation import runner

    def no_git(command, **kwargs):
        raise subprocess.CalledProcessError(128, command)

    monkeypatch.setattr(runner.subprocess, "run", no_git)

    assert runner.git_commit() == "unknown"

    def dirty(command, **kwargs):
        out = "abc123\n" if command[1] == "rev-parse" else " M backend/src/x.py\n"
        return subprocess.CompletedProcess(command, 0, stdout=out, stderr="")

    monkeypatch.setattr(runner.subprocess, "run", dirty)

    assert runner.git_commit() == "abc123-dirty"


# ----------------------------------------------------------------------
# The tuning loop (`run --loop`)
# ----------------------------------------------------------------------


class LoopChecker:
    """
    A scripted checker: each claim's first verdict, second-look verdict
    and verdict on the annotator's pages, by claim text. The pipeline's
    own second look and reference check are tested in
    tests/services/fact_checker/test_second_look.py; this holds what the
    runner makes of their answers.
    """

    def __init__(self, script: dict[str, tuple]):
        self.script = script
        self.second_looks: list[str] = []
        self.references: list[tuple[str, list[str]]] = []

    def check_claim(self, claim, on_phase=None, thresholds=None, *, context=None, language=None):
        first, *_ = self.script[claim.text]
        verdict, confidence = first
        return FactCheck(verdict=verdict, confidence=confidence, explanation="first", claim=claim.text)

    def second_look(self, claim, first, on_phase=None, thresholds=None, *, context=None,
                    language=None, trigger="requested"):
        from src.models.fact_checker.fact_check import SecondLook

        self.second_looks.append(claim.text)
        _, second, *_ = self.script[claim.text]
        return FactCheck(
            verdict=second, confidence=0.8, explanation="second", claim=claim.text,
            second_look=SecondLook(trigger=trigger, first_verdict=first.verdict,
                                   first_confidence=first.confidence, queries=["q"], new_evidence=1),
        )

    def check_against(self, claim, urls, on_phase=None, thresholds=None, *, context=None, language=None):
        self.references.append((claim.text, urls))
        _, _, reference, read = self.script[claim.text]
        return FactCheck(verdict=reference, confidence=0.9, explanation="reference", claim=claim.text), read


def test_the_loop_rechecks_disagreements_and_sorts_what_stays_wrong(repository, tmp_path):

    T, F, U, P = Verdict.TRUE, Verdict.FALSE, Verdict.UNVERIFIED, Verdict.PARTIALLY_TRUE
    links = {"referenceEvidenceLinks": ["https://www.ine.es/informe"]}

    rows = [
        # (gold, first, second look, annotator's pages, pages read)
        ("fact001", "Agreed.", "TRUE", ((T, 0.9), None, None, 0), {}),
        ("fact002", "Fixed.", "TRUE", ((U, 0.0), T, None, 0), {}),
        ("fact003", "Search missed it.", "FALSE", ((T, 0.9), T, F, 1), links),
        ("fact004", "Model and gold differ.", "FALSE", ((T, 0.9), T, T, 1), links),
        ("fact005", "A third answer.", "FALSE", ((T, 0.9), T, P, 1), links),
        ("fact006", "Nothing readable.", "FALSE", ((T, 0.9), T, F, 0), links),
        ("fact007", "No links.", "UNVERIFIED", ((T, 0.9), T, None, 0), {"referenceEvidenceLinks": []}),
        # Agrees with gold, but unsure: a second look for the trigger's sake.
        ("fact008", "Unsure but right.", "TRUE", ((T, 0.3), F, None, 0), {}),
    ]

    dataset = load_dataset(write_jsonl(tmp_path / "set.jsonl", [
        custom_row(fact_id, claim, label=gold, **extra) for fact_id, claim, gold, _, extra in rows
    ]))

    checker = LoopChecker({claim: script for _, claim, _, script, _ in rows})

    runner = runner_for(dataset, checker, tmp_path, thresholds=open_gate(), loop=True)
    runner.run()

    records = latest_records(runner.directory)
    outcome = {fact_id: records[fact_id]["loop"]["outcome"] for fact_id, *_ in rows}

    assert outcome == {
        "fact001": "agreed",
        "fact002": "fixed",
        "fact003": "retrieval",
        "fact004": "adjudicate",
        "fact005": "reasoning",
        "fact006": "unreadable",
        "fact007": "no_reference",
        "fact008": "agreed",
    }

    # A confident, correct verdict costs nothing more; the rest get one look.
    assert "Agreed." not in checker.second_looks
    assert len(checker.second_looks) == 7
    # The annotator's pages only for claims still wrong that have links.
    assert [claim for claim, _ in checker.references] == [
        "Search missed it.", "Model and gold differ.", "A third answer.", "Nothing readable.",
    ]

    # The record's verdict stays the first pass's; the loop sits beside it.
    fixed = records["fact002"]
    assert (fixed["verdict"], fixed["loop"]["secondLook"]["verdict"]) == ("UNVERIFIED", "TRUE")
    assert fixed["loop"]["trigger"] == "unverified"
    assert records["fact008"]["loop"]["trigger"] == "low_confidence"
    assert records["fact003"]["loop"]["reference"]["pagesRead"] == 1
    assert set(fixed["loop"]["usage"]) == set(fixed["usage"])


def test_the_loop_is_keyed_so_it_never_resumes_a_run_without_it(tmp_path):

    dataset = five_rows(tmp_path)
    plain = RunConfig(dataset=dataset, model="m", corpus="none", root=tmp_path)
    looped = RunConfig(dataset=dataset, model="m", corpus="none", root=tmp_path, loop=True)

    assert plain.key != looped.key


def test_a_model_told_not_to_think_is_another_run(tmp_path, monkeypatch):
    """
    qwen3.5:4b thinking and qwen3.5:4b told not to are one name and two
    models' worth of answers; resuming one into the other would mix them.
    A model with no effort set keeps the key it always had.
    """

    from src.config.settings import settings

    dataset = five_rows(tmp_path)
    before = RunConfig(dataset=dataset, model="m", corpus="none", root=tmp_path).key
    other = RunConfig(dataset=dataset, model="other", corpus="none", root=tmp_path).key

    monkeypatch.setattr(settings, "LLM_REASONING_EFFORT", {"m": "none"})

    assert RunConfig(dataset=dataset, model="m", corpus="none", root=tmp_path).key != before
    assert RunConfig(dataset=dataset, model="other", corpus="none", root=tmp_path).key == other


def test_an_oracle_run_reads_the_annotators_pages_and_never_searches(tmp_path):
    """
    `run --oracle`: each claim judged on its own reference links, web
    addresses only and each once, with no search; a row without links
    reaches the model with nothing. Keyed apart from a run that searched.
    """

    from src.evaluation.report import write_report
    from src.evaluation.runner import ORACLE

    T, F = Verdict.TRUE, Verdict.FALSE

    rows = [
        custom_row("fact001", "Read on its pages.", label="FALSE", referenceEvidenceLinks=[
            "https://www.ine.es/informe", "<LINK NOT AVAILABLE>", "https://www.ine.es/informe",
        ]),
        custom_row("fact002", "No links at all.", label="UNVERIFIED", referenceEvidenceLinks=[]),
    ]

    dataset = load_dataset(write_jsonl(tmp_path / "set.jsonl", rows))

    class NoSearch(LoopChecker):
        def check_claim(self, *args, **kwargs):
            raise AssertionError("an oracle run must not search")

    checker = NoSearch({
        "Read on its pages.": (None, None, F, 1),
        "No links at all.": (None, None, Verdict.UNVERIFIED, 0),
    })

    runner = runner_for(dataset, checker, tmp_path, mode=ORACLE)
    runner.run()

    assert checker.references == [
        ("Read on its pages.", ["https://www.ine.es/informe"]),
        ("No links at all.", []),
    ]

    records = runner.results.latest(lambda record: record["id"])

    assert records["fact001"]["verdict"] == "FALSE"
    assert runner.config.key != runner_for(dataset, checker, tmp_path).config.key

    # Closed by the runner, so the model's span is timed as in a searching run.
    closing = [event for event in records["fact001"]["events"] if event["phase"] == "claim_checked"]
    assert closing and closing[0]["data"] == {"verdict": "FALSE", "pagesRead": 1}

    report = (write_report(runner.directory, resamples=50, root=tmp_path / "reports") / "report.md").read_text(encoding="utf-8")

    assert "the annotator's evidence (oracle)" in report
    assert "## Evidence" in report and "Reference link among candidates" not in report
