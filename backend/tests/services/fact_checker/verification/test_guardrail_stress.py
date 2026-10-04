"""
The hallucination guardrails, stress-tested by a model trying to bluff.

The deterministic rules around the LLM - a definitive verdict must cite
something, citations must name a source it was shown, a source it called
unrelated grounds nothing, a quote must be verbatim, the verdict and the
confidence must be in range, and no evidence means no question asked -
were each unit-tested with a well-behaved fake. None had faced an answer
written to get past it.

`BluffingModel` stands in for the model itself (the OpenAI SDK client),
so every answer here takes the path a real one does: the real
`LLMClient` parses the raw text, the real `LLMVerifier` normalises it and
the real `ConfidenceScorer` recalibrates it, inside the real
`FactChecker.check_claim`. Only the evidence (canned, two outlets) and
the model's words are fake.

Found on 2026-10-02 and fixed, each with a test below:

- `[0, 0, 0, ...]` counted every repeat as a citation: a FALSE resting on
  one source went from 0.70 to 1.00 confidence.
- JSON `true` is a Python int: `"cited_evidence": [true]` cited source 1.
- `"cited_evidence": null` or `0`, or an answer that was valid JSON but
  not an object (`"TRUE"`, `[]`), raised - out of the claim's thread,
  failing the whole article and every other claim's verdict with it.
- A quote made of the end of a source's headline and the start of its
  body passed as verbatim: the two were searched as one string.
- A per-run `min_evidence_for_verdict=0` sent a claim with no evidence to
  the model, which answered from its own knowledge.

Still bluffable, pinned as strict xfails at the bottom: they need a
policy decision (what a contradiction between the verdict and the
model's own stances should become), not a small fix.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from src.config.thresholds import PipelineThresholds
from src.models.fact_checker.fact_check import FactCheck, Verdict
from src.models.fact_checker.pipeline_stage import PipelineStage
from src.services.fact_checker.fact_checker import FactChecker
from src.services.fact_checker.verification.confidence_scorer import ConfidenceScorer
from src.services.fact_checker.verification.llm_verification import LLMVerifier
from src.services.llms import LLMClient

from tests.factories import create_claim, create_evidence
from tests.services.fact_checker.fakes import FakeEvidenceRetriever, FakeRanker


class BluffingModel:
    """
    The model behind `LLMClient`, in the OpenAI SDK's shape: answers are
    raw text, consumed in order, the last one repeated (so a retry gets
    the same bluff again). `calls` counts every time it was asked.
    """

    def __init__(self, *answers: str):
        self.answers = list(answers)
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


CLAIM = create_claim(text="87% of the transplanted seagrass shoots survived their first winter.")

# Two outlets, so a TRUE resting on both is not capped as single-sourced.
EVIDENCE = [
    create_evidence(
        url="https://marine-daily.example/seagrass",
        domain="marine-daily.example",
        title="Seagrass transplants survive the winter",
        content=(
            "The institute reported that 87% of the transplanted shoots "
            "survived their first winter in the Sado estuary.\nVolunteer "
            "divers replanted the meadow from 2021."
        ),
        relevance_score=0.8,
    ),
    create_evidence(
        url="https://ocean-review.example/zostera",
        domain="ocean-review.example",
        title="Volunteers replant a lost meadow",
        content="Survival of the Zostera marina shoots was well above earlier European attempts.",
        relevance_score=0.7,
    ),
]

HONEST = {
    "verdict": "TRUE",
    "confidence": 0.8,
    "explanation": "Both sources report the survival rate.",
    "cited_evidence": [0, 1],
    "assessments": [
        {"index": 0, "stance": "supports", "quote": "87% of the transplanted shoots survived their first winter"},
        {"index": 1, "stance": "supports", "quote": ""},
    ],
}


def answer(**overrides) -> str:
    """The honest answer with some fields replaced by a bluff, as JSON."""

    return json.dumps({**HONEST, **overrides})


def judge(
    *answers: str,
    evidence=EVIDENCE,
    thresholds: PipelineThresholds | None = None,
) -> tuple[FactCheck, BluffingModel, list[str]]:
    """One claim through the real judgement path; the verdict, the model, the phases."""

    model = BluffingModel(*answers)

    checker = FactChecker(
        None,
        evidence_retriever=FakeEvidenceRetriever({CLAIM.text: list(evidence)}),
        ranker=FakeRanker(),
        verifier=LLMVerifier(client=LLMClient(client=model)),
        confidence_scorer=ConfidenceScorer(),
    )

    phases: list[str] = []

    check = checker.check_claim(
        CLAIM,
        on_phase=lambda phase, data: phases.append(phase),
        thresholds=thresholds or PipelineThresholds(),
    )

    return check, model, phases


def assert_in_unit_range(check: FactCheck) -> None:

    assert 0.0 <= check.confidence <= 1.0
    assert 0.0 <= check.raw_confidence <= 1.0


def test_the_honest_answer_is_kept():
    """The baseline every bluff below is measured against."""

    check, model, _ = judge(answer())

    assert check.verdict == Verdict.TRUE
    assert check.cited_evidence_indices == [0, 1]
    assert check.reached_stage == PipelineStage.AGGREGATION
    assert len(model.calls) == 1


# ----------------------------------------------------------------------
# A definitive verdict citing nothing
# ----------------------------------------------------------------------


@pytest.mark.parametrize("verdict", ["TRUE", "PARTIALLY_TRUE", "FALSE", "MISLEADING"])
@pytest.mark.parametrize("citations", [[], "missing"])
def test_a_definitive_verdict_citing_nothing_is_unverified(verdict, citations):

    bluff = {**HONEST, "verdict": verdict, "confidence": 1.0}

    if citations == "missing":
        del bluff["cited_evidence"]
    else:
        bluff["cited_evidence"] = citations

    check, _, _ = judge(json.dumps(bluff))

    assert check.verdict == Verdict.UNVERIFIED
    assert check.raw_verdict == Verdict(verdict)
    assert check.confidence <= 0.4
    assert check.stage_note.endswith("it cited no evidence.")


# ----------------------------------------------------------------------
# Citations that name nothing it was shown
# ----------------------------------------------------------------------


@pytest.mark.parametrize("citations", [
    [2, 99],          # past the end
    [-1, -2],         # Python would index from the end
    ["0", "1"],       # strings
    [0.0, 1.0],       # floats
    [True],           # a bool is an int in Python: this used to cite source 1
    [None, [0], {"index": 0}],
], ids=["past-the-end", "negative", "strings", "floats", "bool", "nested"])
def test_citations_naming_no_source_shown_ground_nothing(citations):

    check, _, _ = judge(answer(verdict="FALSE", cited_evidence=citations))

    assert check.cited_evidence_indices == []
    assert check.verdict == Verdict.UNVERIFIED


@pytest.mark.parametrize("citations", [None, 0, "0, 1", {"0": True}])
def test_citations_that_are_not_a_list_do_not_crash_the_claim(citations):
    """`null` and a bare `0` raised, and failed the whole article with it."""

    check, _, _ = judge(answer(verdict="FALSE", cited_evidence=citations))

    assert check.cited_evidence_indices == []
    assert check.verdict == Verdict.UNVERIFIED


def test_a_repeated_citation_counts_once():
    """
    `ConfidenceScorer` scores the citations against the number of sources,
    so ten copies of one index scored as ten sources' worth: a FALSE on
    one source went from 0.70 to 1.00 confidence.
    """

    once, _, _ = judge(answer(verdict="FALSE", cited_evidence=[0]))
    repeated, _, _ = judge(answer(verdict="FALSE", cited_evidence=[0] * 10))

    assert repeated.cited_evidence_indices == [0]
    assert repeated.verdict == once.verdict == Verdict.FALSE
    assert repeated.confidence == once.confidence


def test_repeats_and_strays_cannot_inflate_a_true_verdict():

    honest, _, _ = judge(answer())
    padded, _, _ = judge(answer(cited_evidence=[1, 0, 1, 0, 7, -1, True, 0]))

    assert padded.cited_evidence_indices == [1, 0]
    assert padded.confidence == honest.confidence


def test_a_bool_assessment_index_names_no_source():

    check, _, _ = judge(answer(
        cited_evidence=[1],
        assessments=[{"index": True, "stance": "unrelated", "quote": ""}],
    ))

    # The `true` entry is ignored, not read as "source 1 is unrelated".
    assert check.verdict == Verdict.TRUE
    assert [item.stance for item in check.evidence] == [None, None]


# ----------------------------------------------------------------------
# Citing only sources it called unrelated
# ----------------------------------------------------------------------


@pytest.mark.parametrize("verdict", ["TRUE", "FALSE", "MISLEADING"])
def test_citing_only_sources_it_called_unrelated_is_unverified(verdict):

    check, _, _ = judge(answer(
        verdict=verdict,
        confidence=1.0,
        assessments=[
            {"index": 0, "stance": "UNRELATED", "quote": ""},
            {"index": 1, "stance": "unrelated", "quote": ""},
        ],
    ))

    assert check.verdict == Verdict.UNVERIFIED
    assert check.confidence <= 0.4
    assert "it cited only sources it judged unrelated" in check.stage_note


def test_an_unrelated_source_cited_beside_a_supporting_one_adds_no_corroboration():

    check, _, _ = judge(answer(assessments=[
        {"index": 0, "stance": "supports", "quote": ""},
        {"index": 1, "stance": "unrelated", "quote": ""},
    ]))

    assert check.verdict == Verdict.TRUE
    assert check.independent_domains == 1
    # Single-sourced, so capped.
    assert check.confidence <= 0.6


# ----------------------------------------------------------------------
# Quotes
# ----------------------------------------------------------------------


def quotes(check: FactCheck) -> list[str | None]:

    return [item.quote for item in check.evidence]


def test_a_fabricated_quote_is_dropped():

    check, _, _ = judge(answer(assessments=[
        {"index": 0, "stance": "supports", "quote": "Every single transplanted shoot survived, a world first."},
        {"index": 1, "stance": "supports", "quote": "87% of the transplanted shoots survived their first winter"},
    ]))

    # The second is real - but in source 0, not in source 1 it was given for.
    assert quotes(check) == [None, None]


def test_a_quote_with_one_word_changed_is_dropped():

    check, _, _ = judge(answer(assessments=[
        {"index": 0, "stance": "supports", "quote": "97% of the transplanted shoots survived their first winter"},
    ]))

    assert quotes(check)[0] is None


def test_a_quote_stitched_from_the_headline_and_the_body_is_dropped():
    """
    "...survive the winter" ends source 0's headline and "The institute
    reported..." starts its body. Joined, they read as one sentence that
    is in neither, and it passed as verbatim.
    """

    check, _, _ = judge(answer(assessments=[
        {"index": 0, "stance": "supports", "quote": "Seagrass transplants survive the winter The institute reported"},
    ]))

    assert quotes(check)[0] is None


def test_a_quote_from_the_headline_alone_is_kept():

    check, _, _ = judge(answer(assessments=[
        {"index": 0, "stance": "supports", "quote": "Seagrass transplants survive the winter"},
    ]))

    assert quotes(check)[0] == "Seagrass transplants survive the winter"


@pytest.mark.parametrize("quote", [
    # The source breaks the line after "winter in the Sado estuary."; the
    # model joined it with a space.
    "survived their first winter in the Sado estuary. Volunteer divers replanted the meadow",
    # The model broke a line the source did not.
    "87% of the transplanted\nshoots survived   their first winter",
], ids=["source-newline", "quote-newline"])
def test_a_real_quote_split_over_a_newline_is_kept(quote):

    check, _, _ = judge(answer(assessments=[
        {"index": 0, "stance": "supports", "quote": quote},
    ]))

    assert quotes(check)[0] == " ".join(quote.split())


@pytest.mark.parametrize("quote", ["", "87%", None, 87, ["87% of the shoots"]])
def test_an_empty_short_or_non_text_quote_is_no_quote(quote):

    check, _, _ = judge(answer(assessments=[
        {"index": 0, "stance": "supports", "quote": quote},
    ]))

    assert quotes(check)[0] is None
    assert check.verdict == Verdict.TRUE


# ----------------------------------------------------------------------
# A verdict outside the enum
# ----------------------------------------------------------------------


@pytest.mark.parametrize("verdict", [
    "MOSTLY_TRUE", "TRUE.", "PARTIALLY TRUE", "VERIFIED", "", 1, None, ["TRUE"], {"verdict": "TRUE"},
])
def test_a_verdict_outside_the_enum_is_unverified(verdict):

    check, _, _ = judge(answer(verdict=verdict, confidence=1.0))

    assert check.verdict == Verdict.UNVERIFIED
    assert check.raw_verdict == Verdict.UNVERIFIED


def test_a_lowercase_verdict_is_read_not_rejected():
    """Case is normalised: not a bluff, and rejecting it would cost real verdicts."""

    check, _, _ = judge(answer(verdict="true"))

    assert check.verdict == Verdict.TRUE


# ----------------------------------------------------------------------
# Confidence outside [0, 1]
# ----------------------------------------------------------------------


@pytest.mark.parametrize("raw", [
    "5", "-3", "1e308", "Infinity", "-Infinity", "NaN", '"high"', '"90%"', "null", "true", "[0.9]",
])
def test_any_confidence_ends_up_in_the_unit_range(raw):
    """
    Spliced in as raw JSON text: `Infinity` and `NaN` are not JSON, but
    Python's parser - which is the one reading the model - accepts both.
    """

    text = answer().replace('"confidence": 0.8', f'"confidence": {raw}')

    check, _, _ = judge(text)

    assert check.verdict == Verdict.TRUE
    assert_in_unit_range(check)


def test_an_inflated_confidence_buys_nothing_a_confident_model_could_not_say():
    """Clamped, so `100` is worth exactly `1.0` - and no more."""

    sure, _, _ = judge(answer(confidence=1.0))
    inflated, _, _ = judge(answer(confidence=100))

    assert inflated.confidence == sure.confidence
    assert inflated.raw_confidence == 1.0


# ----------------------------------------------------------------------
# Malformed or empty JSON
# ----------------------------------------------------------------------


@pytest.mark.parametrize("raw", [
    "",
    "   ",
    "TRUE",
    "I believe the claim is TRUE with 90% confidence.",
    '{"verdict": "TRUE", "confidence": 0.9',
    "{verdict: TRUE}",
    "{}",
    "[]",
    '"TRUE"',
    "true",
    "42",
    "null",
], ids=[
    "empty", "blank", "bare-word", "prose", "truncated", "unquoted-keys", "empty-object",
    "empty-list", "json-string", "json-bool", "json-number", "json-null",
])
def test_an_answer_that_is_no_json_object_is_unverified_without_crashing(raw):
    """
    Valid JSON that is not an object (`"TRUE"`, `[]`, `true`, `42`) used to
    raise out of the claim's thread, failing the whole article.
    """

    check, model, phases = judge(raw)

    assert check.verdict == Verdict.UNVERIFIED
    assert check.raw_verdict == Verdict.UNVERIFIED
    assert check.cited_evidence_indices == []
    assert "invalid output" in check.explanation
    assert phases[-1] == "claim_checked"

    # Asked again once, as for any unusable answer. `{}` parses as an
    # object, so it is not retried: it is simply empty.
    assert len(model.calls) == (1 if raw == "{}" else 2)


def test_an_object_wrapped_in_a_list_or_in_prose_is_still_read():
    """Not bluffs - a real model's formatting - and still parsed."""

    in_list, _, _ = judge(f"[{answer()}]")
    in_prose, _, _ = judge(f"Here is my answer:\n{answer()}\nThanks.")

    assert in_list.verdict == in_prose.verdict == Verdict.TRUE


def test_a_garbled_first_answer_is_retried():

    check, model, _ = judge("[]", answer())

    assert check.verdict == Verdict.TRUE
    assert len(model.calls) == 2


@pytest.mark.parametrize("assessments", [
    None, "all supports", 7, [None, "x", 3], [{"index": 0}], [{"stance": "supports"}],
])
def test_a_malformed_assessments_block_keeps_the_verdict(assessments):
    """Degrades to no per-source detail; the citations still decide."""

    check, _, _ = judge(answer(assessments=assessments))

    assert check.verdict == Verdict.TRUE
    assert [item.stance for item in check.evidence] == [None, None]


# ----------------------------------------------------------------------
# No evidence: the model is never asked
# ----------------------------------------------------------------------


@pytest.mark.parametrize("floor", [0, 1, 3])
def test_no_evidence_never_reaches_the_model(floor):
    """
    Whatever the floor - including the 0 a per-run override allows, which
    used to ask the model about a claim with nothing retrieved and take
    its answer from memory at 0.67 confidence.
    """

    check, model, phases = judge(
        answer(verdict="FALSE", confidence=1.0),
        evidence=[],
        thresholds=PipelineThresholds(min_evidence_for_verdict=floor),
    )

    assert len(model.calls) == 0
    assert "verifying_claim" not in phases
    assert check.verdict == Verdict.UNVERIFIED
    assert check.confidence == 0.0
    assert check.reached_stage == PipelineStage.CONFIDENCE_RECALIBRATION
    assert check.stage_note.startswith("No evidence could be retrieved")


def test_evidence_below_the_floor_never_reaches_the_model():

    check, model, _ = judge(
        answer(verdict="FALSE", confidence=1.0),
        thresholds=PipelineThresholds(min_evidence_for_verdict=3),
    )

    assert len(model.calls) == 0
    assert check.verdict == Verdict.UNVERIFIED


# ----------------------------------------------------------------------
# Still bluffable (2026-10-02). Strict xfails: each fails today and will
# fail loudly the day it is fixed, so the marker comes off with the fix.
# ----------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason=(
    "Assessments are de-duplicated first-wins, so a source the model also "
    "called unrelated still grounds a citation if it was called 'supports' first."
))
def test_a_source_it_called_both_supporting_and_unrelated_grounds_nothing():

    check, _, _ = judge(answer(
        cited_evidence=[0],
        assessments=[
            {"index": 0, "stance": "supports", "quote": ""},
            {"index": 0, "stance": "unrelated", "quote": ""},
        ],
    ))

    assert check.verdict == Verdict.UNVERIFIED


@pytest.mark.xfail(strict=True, reason=(
    "No rule checks the verdict against the model's own stances: a FALSE "
    "whose every cited source 'supports' the claim stands."
))
def test_a_false_verdict_whose_cited_sources_all_support_the_claim_does_not_stand():

    check, _, _ = judge(answer(
        verdict="FALSE",
        assessments=[
            {"index": 0, "stance": "supports", "quote": ""},
            {"index": 1, "stance": "supports", "quote": ""},
        ],
    ))

    assert check.verdict != Verdict.FALSE


@pytest.mark.xfail(strict=True, reason=(
    "A TRUE whose every cited source 'contradicts' the claim becomes "
    "PARTIALLY_TRUE (the contradiction rule assumes some support exists)."
))
def test_a_true_verdict_whose_cited_sources_all_contradict_the_claim_is_not_partly_true():

    check, _, _ = judge(answer(assessments=[
        {"index": 0, "stance": "contradicts", "quote": ""},
        {"index": 1, "stance": "contradicts", "quote": ""},
    ]))

    assert check.verdict not in (Verdict.TRUE, Verdict.PARTIALLY_TRUE)
