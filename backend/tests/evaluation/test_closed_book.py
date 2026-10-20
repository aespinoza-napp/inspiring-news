"""
The closed-book condition (src/evaluation/closed_book.py): the model on
the claim alone, as a harness mode whose records pair with every other
run's. The model is a real LLMClient over the stand-in SDK, so JSON mode
and its retry are the production ones.
"""

from __future__ import annotations

import pytest

from src.evaluation import cli
from src.evaluation.closed_book import SYSTEM_PROMPT, ClosedBookJudge
from src.evaluation.dataset import load_dataset
from src.evaluation.metrics import LLM_UNREACHABLE, outcome
from src.evaluation.report import write_report
from src.evaluation.runner import CLOSED_BOOK, MANIFEST
from src.models.fact_checker.fact_check import Verdict
from src.services.llms import LLMUnavailableError

from tests.evaluation.support import StubOpenAI, custom_row, stub_llm, write_jsonl
from tests.evaluation.test_harness_runner import runner_for


class NoPipeline:
    """A checker and claim service that fail if a closed-book run touches them."""

    def check_claim(self, *args, **kwargs):
        raise AssertionError("a closed-book run must not search")

    def check_against(self, *args, **kwargs):
        raise AssertionError("a closed-book run must not read pages")

    def build_claim(self, *args, **kwargs):
        raise AssertionError("a closed-book run needs no entities")


# ----------------------------------------------------------------------
# The judge
# ----------------------------------------------------------------------


def test_the_models_answer_is_the_verdict_with_no_guardrail():

    from src.services.llms import LLMClient

    sdk = StubOpenAI({"verdict": "false", "confidence": 1.7, "recalls_fact_check": True,
                      "fact_checker": "Chequeado", "explanation": "I recall this was debunked."})

    check, recalled = ClosedBookJudge(LLMClient(model="stub-model", client=sdk)).judge(
        "Argentina exported 2 million tonnes of lithium."
    )

    assert check.verdict == check.raw_verdict == Verdict.FALSE
    assert check.confidence == 1.0
    assert check.evidence == [] and not check.llm_unreachable
    assert recalled == {"recallsFactCheck": True, "factChecker": "Chequeado"}

    # The claim alone, under the closed-book prompt, and nothing else.
    sent = sdk.calls[0]["messages"]
    assert sent[0]["content"] == SYSTEM_PROMPT
    assert sent[1]["content"] == "Claim: Argentina exported 2 million tonnes of lithium."


def test_an_answer_outside_the_five_is_invalid_output_scored_unverified():

    from src.services.fact_checker.verification.llm_verification import INVALID_OUTPUT_EXPLANATION

    check, recalled = ClosedBookJudge(stub_llm({"verdict": "PROBABLY"})).judge("A claim.")

    assert check.verdict == Verdict.UNVERIFIED
    assert check.explanation == INVALID_OUTPUT_EXPLANATION
    assert recalled["recallsFactCheck"] is None


def test_an_unreachable_model_is_set_apart_not_scored():

    check, _ = ClosedBookJudge(stub_llm(LLMUnavailableError("connection refused"))).judge("A claim.")

    assert check.llm_unreachable is True
    assert check.verdict == Verdict.UNVERIFIED


# ----------------------------------------------------------------------
# The run
# ----------------------------------------------------------------------


def test_a_closed_book_run_asks_the_model_only_and_reports_it(tmp_path):

    rows = [
        custom_row("fact001", "Remembered.", label="FALSE"),
        custom_row("fact002", "Not known.", label="TRUE"),
    ]
    dataset = load_dataset(write_jsonl(tmp_path / "set.jsonl", rows))

    answers = {
        "Remembered.": {"verdict": "FALSE", "confidence": 0.9, "recalls_fact_check": True},
        "Not known.": {"verdict": "UNVERIFIED", "confidence": 0.1, "recalls_fact_check": False},
    }

    class PerClaim(StubOpenAI):
        def answer(self, kwargs):
            self.content = answers[kwargs["messages"][1]["content"].removeprefix("Claim: ")]
            return super().answer(kwargs)

    from src.services.llms import LLMClient

    judge = ClosedBookJudge(LLMClient(model="stub-model", client=PerClaim(None)))

    runner = runner_for(dataset, NoPipeline(), tmp_path, mode=CLOSED_BOOK, closed_book=judge)
    runner.claims = NoPipeline()
    runner.run()

    records = runner.results.latest(lambda record: record["id"])

    assert records["fact001"]["verdict"] == "FALSE"
    assert records["fact001"]["closedBook"] == {"recallsFactCheck": True, "factChecker": None}
    assert records["fact002"]["evidence"] == [] and records["fact002"]["candidates"] == []

    # Its own run: never resumes into one that searched.
    assert runner.config.key != runner_for(dataset, NoPipeline(), tmp_path).config.key

    # The model's span timed like any run's.
    assert [event["phase"] for event in records["fact001"]["events"]] == ["verifying_claim", "claim_checked"]
    assert records["fact001"]["latency"]["llm"] is not None

    target = write_report(runner.directory, resamples=50, root=tmp_path / "reports")
    report = (target / "report.md").read_text(encoding="utf-8")

    assert "no evidence (closed book)" in report
    assert "remembered a published fact-check of the claim: 1 of 2 answered (fact001)" in report
    assert "## Retrieval" not in report and "## Stage attribution" not in report
    assert (target / MANIFEST).exists()


def test_an_unreachable_model_in_a_closed_book_run_is_set_apart(tmp_path):

    dataset = load_dataset(write_jsonl(tmp_path / "set.jsonl", [custom_row("fact001", "A claim.")]))

    judge = ClosedBookJudge(stub_llm(LLMUnavailableError("down")))
    runner = runner_for(dataset, NoPipeline(), tmp_path, mode=CLOSED_BOOK, closed_book=judge)
    runner.claims = NoPipeline()
    runner.run()

    [record] = runner.results.latest(lambda record: record["id"]).values()

    assert outcome(record) == LLM_UNREACHABLE


@pytest.mark.parametrize("other", ["--oracle", "--retrieval-only", "--loop"])
def test_closed_book_takes_no_other_condition(other, tmp_path):

    dataset = write_jsonl(tmp_path / "set.jsonl", [custom_row("fact001", "A claim.")])

    with pytest.raises(SystemExit, match="--closed-book takes none of"):
        cli.main(["run", "--dataset", str(dataset), "--closed-book", other, "--root", str(tmp_path / "runs")])
