"""
The writing-model benchmark: the text set, the resumable runner, the
rubric and the side-by-side comparison. The corrector under test is the
real TextCorrector; only the OpenAI SDK object behind its LLMClient is
stubbed (tests/evaluation/support.py), so what is metered and parsed is
what production does. Nothing here reaches a live model.
"""

import json
from pathlib import Path

import pytest

from src.evaluation import cli
from src.evaluation.usage import UsageMeter, metered
from src.evaluation.writing import (
    CLEAN,
    ERROR,
    OK,
    UNREACHABLE,
    TextSetError,
    WritingRunner,
    compare_runs,
    load_texts,
    load_writing_run,
    mentioned,
    named,
    render,
    score,
    write_comparison,
)
from src.services.corrector.text_corrector import LLM_METRIC_KEYS, TextCorrector
from src.services.llms import LLMUnavailableError

from tests.evaluation.support import StubOpenAI, write_jsonl
from tests.services.fact_checker.fakes import FakeQualityAnalyzer, FakeSentimentAnalyzer

COMMITTED = Path(__file__).resolve().parents[2] / "data" / "evaluation" / "writing" / "texts_en_es.jsonl"


def text_row(base: str, variant: str, text: str, *, language: str = "en", mentions=()) -> dict:

    targets = {
        CLEAN: None,
        "grammar": "grammar",
        "contradiction": "factConsistency",
        "fabrication": "hallucinationIndex",
        "seo": "seo",
        "style": "style",
    }

    return {
        "id": f"{base}-{variant}",
        "base": base,
        "language": language,
        "variant": variant,
        "target": targets[variant],
        "mentions": list(mentions),
        "text": text,
    }


def small_set(tmp_path: Path, name: str = "texts.jsonl") -> Path:
    """One base, its clean text and two defects: small enough to score by hand."""

    return write_jsonl(tmp_path / name, [
        text_row("a", CLEAN, "CLEAN text about a solar farm."),
        text_row("a", "grammar", "GRAMMAR text, the farm have panels.", mentions=["farm have"]),
        text_row("a", "seo", "SEO text with a vague headline.", mentions=["headline*"]),
    ])


class Judge(StubOpenAI):
    """
    An SDK stand-in that scores by what the text starts with: `scores`
    maps that first word (CLEAN, GRAMMAR, SEO...) to the five scores, and
    `summaries` to a summary per metric. Run with max_workers=1: the
    answer is chosen per call.
    """

    def __init__(self, scores: dict, summaries: dict | None = None, *, drop: tuple = ()):
        super().__init__(content={}, usage=(400, 60))
        self.scores = scores
        self.summaries = summaries or {}
        self.drop = drop

    def answer(self, kwargs):

        first = kwargs["messages"][1]["content"].split()[0]

        self.content = {
            key: {
                "score": value,
                "summary": self.summaries.get(first, {}).get(key, "Fine."),
                "issues": [],
            }
            for key, value in self.scores[first].items()
            if key not in self.drop
        }

        return super().answer(kwargs)


def all_metrics(value: float, **overrides) -> dict:

    return {key: overrides.get(key, value) for key in LLM_METRIC_KEYS}


def corrector_over(sdk, meter: UsageMeter) -> TextCorrector:

    from src.services.llms import LLMClient

    return TextCorrector(
        llm=metered(LLMClient(model="judge", client=sdk), meter),
        sentiment_analyzer=FakeSentimentAnalyzer(None),
        quality_analyzer=FakeQualityAnalyzer(0.5, {}),
    )


def runner_for(texts_path: Path, tmp_path: Path, sdk, model: str = "judge-1") -> WritingRunner:

    meter = UsageMeter()

    return WritingRunner(
        load_texts(texts_path),
        model,
        corrector=corrector_over(sdk, meter),
        meter=meter,
        provider="localhost:11434",
        root=tmp_path / "runs",
        max_workers=1,
        commit="abc123",
    )


class FakeCorrector:
    """Only `llm_metrics`, raising what it is told to - for the status paths."""

    def __init__(self, error: Exception):
        self.error = error
        self.calls = 0

    def llm_metrics(self, text):
        self.calls += 1
        raise self.error


# ----------------------------------------------------------------------
# The text set
# ----------------------------------------------------------------------


def test_the_committed_set_is_six_texts_each_clean_and_five_defects():

    texts = load_texts(COMMITTED)

    bases = {text.base for text in texts.texts}

    assert len(bases) == 6
    assert len(texts.texts) == 36
    assert {text.language for text in texts.texts} == {"en", "es"}

    for base in bases:
        variants = sorted(text.variant for text in texts.texts if text.base == base)
        assert variants == sorted([CLEAN, "grammar", "contradiction", "fabrication", "seo", "style"])


def test_no_defect_phrase_in_the_committed_set_is_also_in_its_clean_text():
    """
    A mention quoted from the defect text must not also be in the clean
    one, or "named" credits a model for repeating correct text. "a
    probado" inside "ha probado" and "WHO" read as "who" did exactly that.
    """

    texts = load_texts(COMMITTED)

    clean = {text.base: text.text for text in texts.texts if text.variant == CLEAN}

    for text in texts.texts:
        for mention in text.mentions:
            if mentioned(mention, text.text):
                assert not mentioned(mention, clean[text.base]), (text.id, mention)


@pytest.mark.parametrize("rows, message", [
    ([text_row("a", "grammar", "x")], "no clean version"),
    ([text_row("a", CLEAN, "x"), {**text_row("a", "grammar", "y"), "target": "style"}], "targets grammar"),
    ([text_row("a", CLEAN, "x"), {**text_row("a", "grammar", "y"), "variant": "typo"}], "unknown variant"),
    ([text_row("a", CLEAN, "x"), {**text_row("a", "grammar", "y"), "id": "a-clean"}], "duplicate ids"),
    ([text_row("a", CLEAN, "x"), {**text_row("a", "grammar", "y"), "id": "other"}, text_row("a", "grammar", "z")],
     "two grammar versions"),
    ([text_row("a", CLEAN, "   ")], "empty text"),
])
def test_a_set_that_cannot_be_scored_is_refused(tmp_path, rows, message):

    with pytest.raises(TextSetError, match=message):
        load_texts(write_jsonl(tmp_path / "bad.jsonl", rows))


def test_mentions_are_whole_words_stems_with_a_star_and_acronyms_as_written():

    assert mentioned("farm have", "says 'the farm have' should be 'has'")
    assert not mentioned("a probado", "should read 'ha probado'")
    assert not mentioned("has issue", "it has issued 14,000 loans")

    assert mentioned("repetit*", "Very repetitive wording.")
    assert not mentioned("repetit", "Very repetitive wording.")

    assert mentioned("WHO", "The quote attributed to the WHO is unsupported.")
    assert not mentioned("WHO", "Patients who walked left sooner.")

    assert mentioned("headline*", "Vague HEADLINES hurt search.")


# ----------------------------------------------------------------------
# Running
# ----------------------------------------------------------------------


def test_every_text_is_judged_once_per_repeat_with_its_tokens(tmp_path):

    judge = Judge({"CLEAN": all_metrics(90), "GRAMMAR": all_metrics(90, grammar=40), "SEO": all_metrics(90, seo=30)})

    runner = runner_for(small_set(tmp_path), tmp_path, judge)

    session = runner.run(repeats=2)

    assert (session["pending"], session["ok"], session["errors"]) == (6, 6, 0)

    records = load_writing_run(runner.directory).records

    assert sorted(record["id"] for record in records) == sorted(
        f"a-{variant}#{repeat}" for variant in (CLEAN, "grammar", "seo") for repeat in (0, 1)
    )

    grammar = next(record for record in records if record["id"] == "a-grammar#0")

    assert grammar["metrics"]["grammar"]["score"] == 40
    assert grammar["usable"] == 5
    assert grammar["target"] == "grammar"
    assert (grammar["usage"]["calls"], grammar["usage"]["promptTokens"], grammar["usage"]["completionTokens"]) == (
        1, 400, 60,
    )

    manifest = json.loads((runner.directory / "run.json").read_text(encoding="utf-8"))

    assert manifest["model"] == "judge-1"
    assert manifest["texts"]["count"] == 3
    assert manifest["sessions"][-1]["usage"]["llmCalls"] == 6


def test_a_second_run_judges_nothing_and_more_repeats_add_only_the_new_ones(tmp_path):

    judge = Judge({"CLEAN": all_metrics(90), "GRAMMAR": all_metrics(80), "SEO": all_metrics(70)})

    runner = runner_for(small_set(tmp_path), tmp_path, judge)

    runner.run(repeats=1)

    assert len(judge.calls) == 3

    again = runner_for(small_set(tmp_path), tmp_path, judge)

    assert again.directory == runner.directory
    assert again.run(repeats=1)["pending"] == 0
    assert again.run(repeats=2)["pending"] == 3

    assert len(judge.calls) == 6


def test_an_unreachable_provider_and_an_error_are_written_and_run_again(tmp_path):

    texts = load_texts(small_set(tmp_path))

    for error, status in ((LLMUnavailableError("down"), UNREACHABLE), (RuntimeError("boom"), ERROR)):

        corrector = FakeCorrector(error)

        runner = WritingRunner(texts, f"m-{status}", corrector=corrector, root=tmp_path / "runs",
                               max_workers=1, commit="abc123")

        session = runner.run()

        assert session[{UNREACHABLE: "unreachable", ERROR: "errors"}[status]] == 3

        records = load_writing_run(runner.directory).records

        assert {record["status"] for record in records} == {status}
        assert all(record["metrics"] is None for record in records)

        assert runner.run()["pending"] == 3


def test_a_stopped_run_starts_nothing_new(tmp_path):

    judge = Judge({"CLEAN": all_metrics(90), "GRAMMAR": all_metrics(80), "SEO": all_metrics(70)})

    runner = runner_for(small_set(tmp_path), tmp_path, judge)

    runner.stop()

    session = runner.run()

    assert (session["ran"], session["stopped"]) == (0, True)
    assert judge.calls == []


def test_a_metric_the_model_left_out_is_unusable_not_a_zero(tmp_path):

    judge = Judge(
        {"CLEAN": all_metrics(90), "GRAMMAR": all_metrics(90, grammar=40), "SEO": all_metrics(90)},
        drop=("seo", "style"),
    )

    runner = runner_for(small_set(tmp_path), tmp_path, judge)

    runner.run()

    records = load_writing_run(runner.directory).records

    assert {record["usable"] for record in records} == {3}

    result = score(load_texts(small_set(tmp_path)), records, resamples=200)

    assert result["formatCompliance"] == 0.0
    assert result["perMetric"]["seo"]["unusable"] == 3

    # The seo pair has no usable score on either side: unscorable, and
    # not counted as a miss.
    assert (result["detection"]["pairs"], result["detection"]["unscorable"]) == (1, 1)
    assert result["detection"]["value"] == 1.0


# ----------------------------------------------------------------------
# The rubric, worked by hand
# ----------------------------------------------------------------------


def test_the_rubric_against_scores_worked_out_by_hand(tmp_path):
    """
    grammar defect: 90 -> 40 on grammar (detected, drop 50); the other
    four metrics move 0, 0, 0, 10 -> off-target 2.5.
    seo defect: 90 -> 90 on seo (a tie, 0.5); the others move 0.
    Detection = (1 + 0.5) / 2 = 0.75. Named: the grammar summary quotes
    "farm have", the seo one says nothing -> 1 of 2.
    """

    judge = Judge(
        {
            "CLEAN": all_metrics(90),
            "GRAMMAR": all_metrics(90, grammar=40, style=80),
            "SEO": all_metrics(90),
        },
        summaries={"GRAMMAR": {"grammar": "Agreement error: 'the farm have panels'."}},
    )

    texts_path = small_set(tmp_path)

    runner = runner_for(texts_path, tmp_path, judge)

    runner.run()

    result = score(load_texts(texts_path), load_writing_run(runner.directory).records, resamples=500)

    assert result["detection"]["value"] == 0.75
    assert result["detection"]["pairs"] == 2
    assert result["detection"]["low"] <= 0.75 <= result["detection"]["high"]

    assert result["perMetric"]["grammar"]["detection"] == 1.0
    assert result["perMetric"]["grammar"]["meanDrop"] == 50
    assert result["perMetric"]["seo"]["detection"] == 0.5
    assert result["perMetric"]["grammar"]["cleanMean"] == 90

    assert result["offTargetDrift"] == 1.25  # (2.5 + 0) / 2

    assert result["named"] == 0.5
    assert result["formatCompliance"] == 1.0

    assert result["consistency"]["meanRange"] is None
    assert result["usage"]["promptTokens"] == 3 * 400


def test_repeats_that_disagree_show_in_consistency(tmp_path):

    texts = load_texts(small_set(tmp_path))

    def record(text_id, repeat, value):
        return {
            "id": f"{text_id}#{repeat}", "textId": text_id, "repeat": repeat, "status": OK,
            "metrics": {key: {"score": value, "summary": "", "issues": [], "usable": True} for key in LLM_METRIC_KEYS},
            "usable": 5, "latency": {"total": 1.0}, "usage": {},
        }

    records = [record("a-clean", 0, 90), record("a-clean", 1, 80), record("a-grammar", 0, 50), record("a-grammar", 1, 50)]

    result = score(texts, records, resamples=100)

    # a-clean ranges 10 on every metric, a-grammar 0: mean 5.
    assert result["consistency"]["meanRange"] == 5
    assert result["consistency"]["textsRepeated"] == 2
    assert result["units"]["repeats"] == 2


def test_named_reads_the_targeted_metric_only():

    texts = {text["id"]: text for text in [text_row("a", "grammar", "x", mentions=["farm have"])]}

    from src.evaluation.writing import Text

    text = Text(**{**texts["a-grammar"], "mentions": ("farm have",)})

    on_target = {"metrics": {"grammar": {"summary": "", "issues": ["'farm have' should be 'farm has'"]}}}
    elsewhere = {"metrics": {"grammar": {"summary": "Fine.", "issues": []},
                             "style": {"summary": "farm have", "issues": []}}}

    assert named(on_target, text)
    assert not named(elsewhere, text)


# ----------------------------------------------------------------------
# The comparison
# ----------------------------------------------------------------------


def two_runs(tmp_path: Path) -> tuple[Path, Path, Path]:

    texts_path = small_set(tmp_path)

    blind = Judge({"CLEAN": all_metrics(80), "GRAMMAR": all_metrics(80), "SEO": all_metrics(80)})
    sharp = Judge({"CLEAN": all_metrics(90), "GRAMMAR": all_metrics(90, grammar=30), "SEO": all_metrics(90, seo=50)})

    first = runner_for(texts_path, tmp_path, blind, model="blind")
    second = runner_for(texts_path, tmp_path, sharp, model="sharp")

    first.run()
    second.run()

    return texts_path, first.directory, second.directory


def test_runs_are_compared_side_by_side_and_paired_against_the_first(tmp_path):

    texts_path, blind, sharp = two_runs(tmp_path)

    prices = {"sharp": {"inputPerMTok": 1.0, "outputPerMTok": 2.0, "currency": "USD"}}

    result = compare_runs([blind, sharp], prices=prices, resamples=300)

    rows = {row["model"]: row for row in result["runs"]}

    assert rows["blind"]["detection"]["value"] == 0.5
    assert rows["sharp"]["detection"]["value"] == 1.0

    assert rows["blind"]["usage"]["cost"] is None  # no price: n/a, never 0
    assert rows["sharp"]["usage"]["cost"]["total"] == pytest.approx((3 * 400 * 1.0 + 3 * 60 * 2.0) / 1_000_000)

    versus = rows["sharp"]["vsBaseline"]

    assert (versus["baseline"], versus["pairs"], versus["difference"]) == ("blind", 2, 0.5)
    assert "vsBaseline" not in rows["blind"]

    markdown = render(result)

    assert "`blind`" in markdown and "`sharp`" in markdown
    assert "+50 pts" in markdown


def test_runs_over_different_text_sets_are_not_compared(tmp_path):

    _, blind, _ = two_runs(tmp_path)

    other = write_jsonl(tmp_path / "other.jsonl", [
        text_row("b", CLEAN, "CLEAN another text."),
        text_row("b", "seo", "SEO another text."),
    ])

    judge = Judge({"CLEAN": all_metrics(90), "SEO": all_metrics(50)})

    elsewhere = runner_for(other, tmp_path, judge, model="other")
    elsewhere.run()

    with pytest.raises(ValueError, match="same text set"):
        compare_runs([blind, elsewhere.directory], resamples=10)


def test_the_cli_runs_and_reports(tmp_path, monkeypatch, capsys):

    texts_path = small_set(tmp_path)

    judge = Judge({"CLEAN": all_metrics(90), "GRAMMAR": all_metrics(90, grammar=40), "SEO": all_metrics(90, seo=40)})

    built = {}

    def build(texts, model, root=None):
        runner = runner_for(texts.path, tmp_path, judge, model=model)
        built["runner"] = runner
        return runner

    monkeypatch.setattr(cli, "build_writing_runner", build)
    monkeypatch.setattr(cli, "_stop_on_first_interrupt", lambda stop: None)

    assert cli.main(["writing", "run", "--model", "llama3.2:3b", "--texts", str(texts_path), "--repeats", "2"]) == 0

    printed = json.loads(capsys.readouterr().out)

    assert (printed["ok"], printed["run"]) == (6, str(built["runner"].directory))

    out = tmp_path / "reports"

    assert cli.main([
        "writing", "report", "--run", str(built["runner"].directory), "--resamples", "50", "--out", str(out),
    ]) == 0

    assert (out / "texts" / "comparison.md").exists()
    assert json.loads((out / "texts" / "comparison.json").read_text(encoding="utf-8"))["runs"][0]["model"] == "llama3.2:3b"


def test_write_comparison_files_the_report_by_text_set(tmp_path):

    _, blind, sharp = two_runs(tmp_path)

    target = write_comparison([blind, sharp], resamples=20, root=tmp_path / "reports")

    assert target == tmp_path / "reports" / "texts"
    assert "Writing models compared: texts" in (target / "comparison.md").read_text(encoding="utf-8")


def test_a_crlf_checkout_of_the_text_set_hashes_like_an_lf_one(tmp_path):

    # Bytes, not write_text: on Windows text mode would already be CRLF.
    lines = small_set(tmp_path).read_bytes().replace(b"\r\n", b"\n")

    unix = tmp_path / "unix" / "texts.jsonl"
    unix.parent.mkdir()
    unix.write_bytes(lines)

    windows = tmp_path / "windows" / "texts.jsonl"
    windows.parent.mkdir()
    windows.write_bytes(lines.replace(b"\n", b"\r\n"))

    assert b"\r\n" not in unix.read_bytes() and b"\r\n" in windows.read_bytes()

    assert load_texts(windows).sha256 == load_texts(unix).sha256
