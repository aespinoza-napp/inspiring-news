import pytest

from src.config.thresholds import PipelineThresholds
from src.services.fact_checker.verification import excerpts
from src.services.fact_checker.verification.llm_verification import LLMVerifier

from tests.factories import create_claim, create_evidence
from tests.services.fact_checker.fakes import FakeLLMClient

# Written against the list verifier, one call for every source (conftest.py).
pytestmark = pytest.mark.usefixtures("list_verifier")

# A page whose opening is about something else, with the sentence that
# addresses the claim far down - the shape the head of a page misses.
FILLER = " ".join(f"Paragraph {n} talks about the weather in general terms." for n in range(40))
ADDRESSED = "NASA confirmed in 2024 that the water found on Mars was frozen."
PAGE = f"Home. Subscribe now. {FILLER} {ADDRESSED} The end of the page."


def test_a_text_within_the_budget_is_kept_whole():

    text = "Short page. Nothing to choose."

    assert excerpts.passages(text, 500, ["NASA"], ["water"]) == text


def test_passages_keep_the_sentence_that_carries_the_claim():

    excerpt = excerpts.passages(PAGE, 400, ["NASA", "2024"], ["water", "Mars"])

    assert ADDRESSED in excerpt
    assert len(excerpt) <= 400
    assert ADDRESSED not in excerpts.head(PAGE, 400)


def test_leftover_budget_goes_to_the_opening_in_page_order():

    excerpt = excerpts.passages(PAGE, 400, ["NASA"], ["water"])

    # The opening is shown first, the passage after it, a gap between.
    assert excerpt.startswith("Home.")
    assert excerpt.index("Home.") < excerpt.index(ADDRESSED)
    assert excerpts.GAP in excerpt


def test_neighbouring_sentences_are_joined_without_a_gap():

    text = "Alpha one. NASA found water. Mars is cold. " + "Filler sentence here. " * 30

    excerpt = excerpts.passages(text, 80, ["NASA"], ["water", "Mars"])

    assert "NASA found water. Mars is cold." in excerpt


def test_a_page_with_none_of_the_claims_terms_gets_its_head():

    assert excerpts.passages(PAGE, 300, ["Jupiter"], ["helium"]) == excerpts.head(PAGE, 300)


def test_every_sentence_shown_is_whole():

    excerpt = excerpts.passages(PAGE, 400, ["NASA"], ["water"])

    for part in excerpt.split(excerpts.GAP):
        assert part in PAGE


def _prompt(thresholds: PipelineThresholds) -> str:

    client = FakeLLMClient(responses={"verdict": "TRUE", "confidence": 0.5, "explanation": "", "cited_evidence": [0]})

    LLMVerifier(client=client).verify(
        create_claim(text="NASA discovered water on Mars in 2024."),
        [create_evidence(content=PAGE)],
        thresholds=thresholds,
        language="en",
    )

    [(_, user_prompt)] = client.calls

    return user_prompt


def test_the_default_shows_the_model_the_first_characters_as_before():

    prompt = _prompt(PipelineThresholds(verifier_excerpt="head", verifier_excerpt_chars=1500))

    assert PAGE[:1500] in prompt
    assert ADDRESSED not in prompt


def test_passages_show_the_model_what_addresses_the_claim_in_fewer_characters():

    head = _prompt(PipelineThresholds(verifier_excerpt="head", verifier_excerpt_chars=1500))
    passages = _prompt(PipelineThresholds(verifier_excerpt="passages", verifier_excerpt_chars=700))

    assert ADDRESSED in passages
    assert len(passages) < len(head)


def test_a_quote_from_a_passage_is_still_found_in_the_page():

    client = FakeLLMClient(responses={
        "verdict": "TRUE",
        "confidence": 0.8,
        "explanation": "",
        "cited_evidence": [0],
        "assessments": [{"index": 0, "stance": "supports", "quote": ADDRESSED}],
    })

    result = LLMVerifier(client=client).verify(
        create_claim(),
        [create_evidence(content=PAGE)],
        thresholds=PipelineThresholds(verifier_excerpt="passages", verifier_excerpt_chars=700),
    )

    assert result.assessments[0].quote == ADDRESSED
