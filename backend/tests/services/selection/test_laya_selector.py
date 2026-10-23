"""
The AI selection's Laya option (src/services/selection/laya_selector.py),
against a stand-in for inference/'s /decisions.
"""

import pytest

from src.config.decisions import WORTH_OFFERING
from src.services.inference_client import InferenceUnavailable
from src.services.selection.laya_selector import CHECKPOINT, LayaSelector


class FakeClient:

    def __init__(self, levels=None, error=None):
        self.levels = levels or {}
        self.error = error
        self.calls = []

    def decide_many(self, checkpoint, states, questions):
        self.calls.append((checkpoint, states, questions))
        if self.error:
            raise self.error
        return [{"worth_offering": {"type": "score", "score": self.levels[state.split("\n")[0]]}} for state in states]


def candidate(title, summary=None):
    return {"url": f"https://news.example/{title}", "title": title, "summary": summary}


def test_every_candidate_is_scored_on_the_llms_scale_and_the_best_picked():

    client = FakeClient({"low": 0.1, "worth": 1.0, "best": 1.9, "good": 1.5})
    candidates = [candidate("low"), candidate("worth", "A summary."), candidate("best"), candidate("good")]

    selection = LayaSelector(client).select(candidates, ["science"], limit=1, min_score=6.0)

    # Levels 0-2 times five: 1.9 -> 9.5 and 1.5 -> 7.5 reach 6; the limit keeps one.
    assert [item.score for item in selection.scored] == [0.5, 5.0, 9.5, 7.5]
    assert [item.url for item in selection.picks] == ["https://news.example/best"]
    assert selection.model == f"laya:{CHECKPOINT}" and selection.calls == 1


def test_it_asks_the_trained_question_about_the_trained_state():

    client = FakeClient({"worth": 1.0})

    LayaSelector(client).select([candidate("worth", "  A summary. ")], ["health"], limit=5)

    checkpoint, states, questions = client.calls[0]
    assert checkpoint == "worth_offering"
    assert states == ["worth\nA summary."]
    assert questions == {"worth_offering": WORTH_OFFERING}


def test_inference_unreachable_is_raised_not_an_empty_selection():

    with pytest.raises(InferenceUnavailable):
        LayaSelector(FakeClient(error=InferenceUnavailable("down"))).select([candidate("x")], ["health"], limit=5)
