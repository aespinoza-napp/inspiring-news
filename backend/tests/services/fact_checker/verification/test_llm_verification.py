from src.models.fact_checker.fact_check import Verdict
from src.services.fact_checker.claim_selector import ArticleContext
from src.services.fact_checker.verification.llm_verification import LLMVerifier
from src.services.llms import LLMUnavailableError

from tests.factories import create_claim, create_evidence
from tests.services.fact_checker.fakes import FakeLLMClient


def test_verify_returns_normalized_result_on_valid_response():

    client = FakeLLMClient(responses={
        "verdict": "TRUE",
        "confidence": 0.85,
        "explanation": "Confirmed by evidence [0].",
        "cited_evidence": [0],
    })

    verifier = LLMVerifier(client=client)

    evidence = [create_evidence()]

    result = verifier.verify(create_claim(), evidence)

    assert result.verdict == Verdict.TRUE
    assert result.confidence == 0.85
    assert result.explanation == "Confirmed by evidence [0]."
    assert result.cited_evidence == [0]


def test_verify_defaults_to_unverified_on_invalid_verdict_string():

    client = FakeLLMClient(responses={
        "verdict": "MAYBE",
        "confidence": 0.9,
        "explanation": "unsure",
        "cited_evidence": [],
    })

    verifier = LLMVerifier(client=client)

    result = verifier.verify(create_claim(), [create_evidence()])

    assert result.verdict == Verdict.UNVERIFIED


def test_verify_clamps_out_of_range_confidence():

    client = FakeLLMClient(responses={
        "verdict": "FALSE",
        "confidence": 5.0,
        "explanation": "way too confident",
        "cited_evidence": [],
    })

    verifier = LLMVerifier(client=client)

    result = verifier.verify(create_claim(), [create_evidence()])

    assert result.confidence == 1.0


def test_verify_filters_out_of_range_cited_evidence_indices():

    evidence = [create_evidence(), create_evidence()]

    client = FakeLLMClient(responses={
        "verdict": "TRUE",
        "confidence": 0.7,
        "explanation": "ok",
        "cited_evidence": [0, 1, 5, -1],
    })

    verifier = LLMVerifier(client=client)

    result = verifier.verify(create_claim(), evidence)

    assert result.cited_evidence == [0, 1]


def test_verify_falls_back_to_unverified_when_client_returns_none():

    client = FakeLLMClient(responses=None)

    verifier = LLMVerifier(client=client)

    result = verifier.verify(create_claim(), [create_evidence()])

    assert result.verdict == Verdict.UNVERIFIED
    assert result.confidence == 0.0


def test_verify_marks_llm_unreachable_distinctly_from_a_real_unverified():
    """
    A dead socket and a model that found no support both surface as
    UNVERIFIED, but only one of them should set llm_unreachable - that
    flag is what lets a caller (or a Phase 4 benchmark) tell them apart.
    """

    client = FakeLLMClient(responses=LLMUnavailableError("connection refused"))

    verifier = LLMVerifier(client=client)

    result = verifier.verify(create_claim(), [create_evidence()])

    assert result.verdict == Verdict.UNVERIFIED
    assert result.llm_unreachable is True


def test_verify_does_not_mark_unreachable_for_an_ordinary_unverified():

    client = FakeLLMClient(responses=None)

    result = LLMVerifier(client=client).verify(create_claim(), [create_evidence()])

    assert result.verdict == Verdict.UNVERIFIED
    assert result.llm_unreachable is False


def test_verify_handles_missing_confidence_field():

    client = FakeLLMClient(responses={
        "verdict": "UNVERIFIED",
        "explanation": "no confidence given",
    })

    verifier = LLMVerifier(client=client)

    result = verifier.verify(create_claim(), [])

    assert result.confidence == 0.0


def test_verify_builds_prompt_with_no_evidence_marker():

    client = FakeLLMClient(responses={"verdict": "UNVERIFIED", "confidence": 0.0, "explanation": "n/a"})

    verifier = LLMVerifier(client=client)

    verifier.verify(create_claim(), [])

    _, user_prompt = client.calls[0]
    assert "(no evidence retrieved)" in user_prompt


# ----------------------------------------------------------------------
# Per-source assessments
# ----------------------------------------------------------------------


def test_a_quote_not_present_in_the_source_is_dropped():
    """
    A small local model will produce a plausible sentence and present it
    as a quotation. An invented quote is worse than no quote: it is the
    one part of this output a reader would take at face value without
    clicking through to check it.
    """

    evidence = [create_evidence(content="The grid ran on 50% renewables in 2024.")]

    client = FakeLLMClient(responses={
        "verdict": "TRUE",
        "confidence": 0.9,
        "explanation": "Confirmed.",
        "cited_evidence": [0],
        "assessments": [
            {
                "index": 0,
                "stance": "supports",
                "quote": "Officials hailed it as a historic milestone.",
            },
        ],
    })

    result = LLMVerifier(client=client).verify(create_claim(), evidence)

    assert result.assessments[0].stance.value == "supports"
    assert result.assessments[0].quote is None


def test_a_quote_present_in_the_source_is_kept():

    evidence = [create_evidence(content="The grid ran on 50% renewables in 2024.")]

    client = FakeLLMClient(responses={
        "verdict": "TRUE",
        "confidence": 0.9,
        "explanation": "Confirmed.",
        "cited_evidence": [0],
        "assessments": [
            {"index": 0, "stance": "supports", "quote": "ran on 50% renewables"},
        ],
    })

    result = LLMVerifier(client=client).verify(create_claim(), evidence)

    assert result.assessments[0].quote == "ran on 50% renewables"


def test_a_malformed_assessments_block_does_not_lose_the_verdict():
    """
    The per-source block is the most likely part of the response for a
    local model to get wrong. Losing the verdict that came back with it
    would make the whole response fail on the model's weakest output.
    """

    client = FakeLLMClient(responses={
        "verdict": "FALSE",
        "confidence": 0.8,
        "explanation": "Contradicted.",
        "cited_evidence": [0],
        "assessments": "not a list at all",
    })

    result = LLMVerifier(client=client).verify(
        create_claim(), [create_evidence()]
    )

    assert result.verdict == Verdict.FALSE
    assert result.confidence == 0.8
    assert result.assessments == []


def test_assessments_pointing_at_evidence_that_does_not_exist_are_discarded():

    client = FakeLLMClient(responses={
        "verdict": "TRUE",
        "confidence": 0.7,
        "explanation": "Confirmed.",
        "cited_evidence": [0],
        "assessments": [
            {"index": 0, "stance": "supports", "quote": ""},
            {"index": 99, "stance": "contradicts", "quote": ""},
            {"index": 0, "stance": "contradicts", "quote": ""},
        ],
    })

    result = LLMVerifier(client=client).verify(
        create_claim(), [create_evidence()]
    )

    # Out of range dropped, and the duplicate index does not get a
    # second, conflicting stance for the same source.
    assert [a.index for a in result.assessments] == [0]
    assert result.assessments[0].stance.value == "supports"


def test_the_model_is_shown_the_article_the_claim_came_from():
    """
    A lone sentence about prize-money contests in Mexico City was
    confirmed by the city's marathon. The model can only judge the claim
    about the article's subject if it is told what that subject is.
    """

    client = FakeLLMClient(responses=None)

    LLMVerifier(client=client).verify(
        create_claim(text="En agosto de 2026 ya había convocatorias."),
        [create_evidence()],
        context=ArticleContext(
            title="Farmear aura: qué es y por qué se volvió viral en 2026",
            lead="Hay algo que los jóvenes están haciendo en las plazas.",
        ),
    )

    [(system_prompt, user_prompt)] = client.calls

    assert "Headline: Farmear aura" in user_prompt
    assert "Opening: Hay algo que los jóvenes" in user_prompt
    assert user_prompt.index("Headline:") < user_prompt.index("Claim:")
    assert "different event" in system_prompt


def test_a_bare_claim_gets_no_article_block():

    client = FakeLLMClient(responses=None)

    LLMVerifier(client=client).verify(create_claim(), [create_evidence()])

    [(_, user_prompt)] = client.calls

    assert user_prompt.startswith("Claim:")


# ----------------------------------------------------------------------
# The compact answer (verifier_answer: compact, 2026-10-22)
# ----------------------------------------------------------------------


def _compact():

    from src.config.thresholds import PipelineThresholds

    return PipelineThresholds(verifier_answer="compact")


def test_the_compact_answer_is_asked_for_with_its_own_short_prompt_and_cap():
    """
    The answer is most of a call on a CPU, so the compact one is asked
    for in a prompt of its own and capped low: a loop stops sooner.
    """

    from src.services.fact_checker.verification.llm_verification import (
        COMPACT_MAX_ANSWER_TOKENS,
        COMPACT_SYSTEM_PROMPT,
        SYSTEM_PROMPT,
    )

    client = FakeLLMClient(responses={"verdict": "TRUE", "confidence": 0.8, "stances": ["supports"], "cited": [0], "reason": "ok"})

    LLMVerifier(client=client).verify(create_claim(), [create_evidence(domain="example.com")], thresholds=_compact())

    system, user = client.calls[0]

    assert system == COMPACT_SYSTEM_PROMPT
    assert len(COMPACT_SYSTEM_PROMPT) < len(SYSTEM_PROMPT)
    assert client.max_tokens == [COMPACT_MAX_ANSWER_TOKENS]
    # The outlet, not the URL: a path is tokens judged on nothing.
    assert "(example.com)" in user
    assert "URL:" not in user


def test_a_compact_answer_becomes_the_same_result_as_a_full_one():
    """
    `stances` in evidence order are the per-source assessments, `cited`
    the citations, `reason` the explanation - so the scorer, the trace
    and the reader see one shape whichever was asked.
    """

    evidence = [create_evidence(url="https://a.example/1"), create_evidence(url="https://b.example/2")]

    client = FakeLLMClient(responses={
        "verdict": "TRUE",
        "confidence": 0.8,
        "stances": ["supports", "unrelated"],
        "cited": [0, 0, 7],
        "reason": "Source 0 reports the figure.",
    })

    result = LLMVerifier(client=client).verify(create_claim(), evidence, thresholds=_compact())

    assert result.verdict == Verdict.TRUE
    assert result.explanation == "Source 0 reports the figure."
    assert result.cited_evidence == [0]
    assert [(item.index, item.stance.value, item.quote) for item in result.assessments] == [
        (0, "supports", None),
        (1, "unrelated", None),
    ]


def test_a_stance_that_is_not_one_is_dropped_not_guessed():

    client = FakeLLMClient(responses={"verdict": "FALSE", "confidence": 0.6, "stances": ["refutes", "contradicts"], "cited": [1], "reason": "x"})

    result = LLMVerifier(client=client).verify(
        create_claim(), [create_evidence(), create_evidence()], thresholds=_compact()
    )

    assert [(item.index, item.stance.value) for item in result.assessments] == [(1, "contradicts")]


def test_the_claims_time_left_reaches_the_client():

    client = FakeLLMClient(responses={"verdict": "TRUE", "confidence": 0.8})

    LLMVerifier(client=client).verify(create_claim(), [create_evidence()], timeout=9.5)
    LLMVerifier(client=client).verify(create_claim(), [create_evidence()])

    assert client.timeouts == [9.5, None]


def test_the_call_record_rides_on_the_result_when_the_client_keeps_one():

    class RecordingClient(FakeLLMClient):
        def last_call(self):
            return {"model": "m", "wait": 1.5, "seconds": 7.25, "promptTokens": 400, "completionTokens": 50}

    result = LLMVerifier(client=RecordingClient(responses={"verdict": "TRUE", "confidence": 0.8})).verify(
        create_claim(), [create_evidence()]
    )

    assert result.call == {"model": "m", "wait": 1.5, "seconds": 7.25, "promptTokens": 400, "completionTokens": 50}

    # A client that keeps none (the shared fake): no record, no error.
    assert LLMVerifier(client=FakeLLMClient(responses={"verdict": "TRUE"})).verify(
        create_claim(), [create_evidence()]
    ).call is None
