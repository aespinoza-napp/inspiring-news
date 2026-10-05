import re

import pytest

from src.services.llms import LLMUnavailableError
from src.services.selection.ai_selector import BATCH, AISelector, _match, prompt


def candidate(n: int, title: str | None = None, **extra) -> dict:

    return {
        "url": f"https://news.example/{n}",
        "title": title or f"Story {n}",
        "source": "example",
        "sourceName": "Example",
        "language": "en",
        "summary": f"Summary of story {n}.",
        **extra,
    }


class TitleScoringLLM:
    """
    Answers from the prompt itself - a score per numbered line, read from
    the title ("Story 7" scores 7 % 11) - so its answers do not depend on
    the order the concurrent batches reach it in.
    """

    model = "fake-model"

    def __init__(self, scores_by_title=None, answer=None):
        self.scores_by_title = scores_by_title or {}
        self.answer = answer
        self.prompts = []

    def complete_json(self, system_prompt, user_prompt, max_retries=1):

        self.prompts.append((system_prompt, user_prompt))

        if self.answer is not None:
            return self.answer(user_prompt)

        scores = []

        for number, title in re.findall(r"^(\d+)\. \[\w+\] (.+?) \(", user_prompt, re.M):
            score = self.scores_by_title.get(title, int(title.split()[-1]) % 11 if title.split()[-1].isdigit() else 0)
            scores.append({"i": int(number), "score": score, "reason": f"because {title}"})

        return {"scores": scores}


def test_the_best_candidates_above_the_minimum_are_picked_best_first():

    candidates = [candidate(n) for n in (3, 9, 7, 10, 5)]

    selection = AISelector(TitleScoringLLM()).select(candidates, ["environment"], limit=2, min_score=6)

    assert [pick.url for pick in selection.picks] == ["https://news.example/10", "https://news.example/9"]
    assert [item.score for item in selection.scored] == [3, 9, 7, 10, 5]
    assert selection.picks[0].reason == "because Story 10"


def test_fewer_than_the_limit_are_picked_when_fewer_reach_the_minimum():

    candidates = [candidate(n) for n in (1, 2, 8)]

    selection = AISelector(TitleScoringLLM()).select(candidates, ["science"], limit=20, min_score=6)

    assert [pick.url for pick in selection.picks] == ["https://news.example/8"]


def test_a_long_list_is_scored_in_batches_and_matched_back_in_order():

    candidates = [candidate(n) for n in range(1, 2 * BATCH + 4)]
    llm = TitleScoringLLM()

    selection = AISelector(llm).select(candidates, ["science"], limit=20)

    assert selection.calls == len(llm.prompts) == 3
    assert [item.url for item in selection.scored] == [c["url"] for c in candidates]
    assert [item.score for item in selection.scored] == [n % 11 for n in range(1, 2 * BATCH + 4)]


def test_the_prompt_names_the_topics_and_each_candidates_language_title_and_summary():

    text = prompt([candidate(1, "Mangroves cut storm waves", language="en"), candidate(2, "El delta recupera aves", language="es")], ["environment", "science"])

    assert text.startswith("Chosen topics: Environment, Science.")
    assert "1. [en] Mangroves cut storm waves (Example)" in text
    assert "2. [es] El delta recupera aves (Example)" in text
    assert "   Summary of story 1." in text


def test_what_the_model_got_wrong_is_left_unscored_not_guessed():

    batch = [candidate(n) for n in (1, 2, 3, 4)]

    answer = {"scores": [
        {"i": 1, "score": 8, "reason": "a solution that works"},
        {"i": 2, "score": "high"},           # not a number
        {"i": 9, "score": 9},                # no such item
        {"i": 3, "score": 4}, {"i": 3, "score": 9},   # scored twice
        {"i": True, "score": 7},             # a bool is not a number here
        {"i": 4, "score": 14},               # clamped to the scale
    ]}

    scored = _match(batch, answer)

    assert [(item.score, item.reason) for item in scored] == [
        (8.0, "a solution that works"), (None, None), (None, None), (10.0, None),
    ]


def test_an_answer_with_no_usable_json_leaves_its_batch_unscored_and_says_so():

    selection = AISelector(TitleScoringLLM(answer=lambda _: None)).select([candidate(9)], ["health"], limit=5)

    assert selection.picks == []
    assert selection.unusable == 1
    assert any("no usable JSON" in note for note in selection.notes)


def test_an_unreachable_model_fails_the_selection_rather_than_picking_from_part_of_it():

    def unreachable(_):
        raise LLMUnavailableError("connection refused")

    with pytest.raises(LLMUnavailableError):
        AISelector(TitleScoringLLM(answer=unreachable)).select([candidate(9)], ["health"], limit=5)
