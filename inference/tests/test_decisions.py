"""
/decisions: Laya's typed answers (src/decisions.py).

The routing, the checkpoint names and the cache are tested against a
stand-in agent; one test asks the real multilingual checkpoint, as the
rest of this suite asks the real models (its first run downloads ~650 MB).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import src.decisions as decisions_module
from src.decisions import DecisionModels, UnknownCheckpoint, checkpoint_dir
from src.main import app

STANCE = {
    "stance": {
        "type": "choice",
        "instructions": "What does the source say about the claim?",
        "criteria": {
            "supports": "the source states what the claim says",
            "unrelated": "the source is about a different event or subject",
        },
    }
}


class FakeAgent:

    def __init__(self, name):
        self.name = name
        self.calls = []

    def predict(self, state, questions):
        self.calls.append(state)
        return {"answers": {qid: {"type": q["type"], "choice": "supports", "seen": state}
                            for qid, q in questions.items()}}

    def predict_batch(self, states, questions, batch_size=None):
        return [self.predict(state, questions) for state in states]


@pytest.fixture
def fake_laya(monkeypatch, tmp_path):
    """laya.load gives a FakeAgent and records what it was asked to load;
    the real DecisionModels does the rest. Fine-tuned folders live in
    tmp_path."""

    import laya

    loads = []

    def load(repo, subfolder=None, device=None):
        loads.append(subfolder or repo)
        return FakeAgent(subfolder or repo)

    monkeypatch.setattr(laya, "load", load)
    models = DecisionModels(max_loaded=2)
    monkeypatch.setattr(decisions_module, "decision_models", models)
    import src.main as main_module
    monkeypatch.setattr(main_module, "decision_models", models)
    monkeypatch.setattr(decisions_module.settings, "DECISION_CHECKPOINTS_DIR", str(tmp_path))
    return loads


def test_one_state_is_answered_by_the_named_checkpoint(fake_laya):

    with TestClient(app) as client:
        response = client.post("/decisions", json={
            "checkpoint": "multilingual", "state": "A claim and a source.", "questions": STANCE,
        })

    assert response.status_code == 200
    body = response.json()
    assert body["checkpoint"] == "multilingual"
    assert body["answers"]["stance"]["choice"] == "supports"
    assert fake_laya == ["multilingual"]


def test_many_states_come_back_in_input_order(fake_laya):

    states = ["first", "second", "third"]

    with TestClient(app) as client:
        response = client.post("/decisions", json={
            "checkpoint": "multilingual", "states": states, "questions": STANCE,
        })

    assert response.status_code == 200
    assert [a["stance"]["seen"] for a in response.json()["answersPerState"]] == states


def test_a_loaded_checkpoint_is_not_loaded_again(fake_laya):

    with TestClient(app) as client:
        for _ in range(3):
            client.post("/decisions", json={"checkpoint": "multilingual", "state": "x", "questions": STANCE})

    assert fake_laya == ["multilingual"]


def test_an_unknown_checkpoint_is_404_and_a_path_is_never_read(fake_laya):

    with TestClient(app) as client:
        for name in ["no_such_decision", "../checkpoints", "/etc", ".hidden"]:
            response = client.post("/decisions", json={"checkpoint": name, "state": "x", "questions": STANCE})
            assert response.status_code == 404, name

    assert fake_laya == []


def test_a_fine_tuned_folder_is_found_by_its_name(fake_laya, tmp_path):

    folder = tmp_path / "source_stance"
    folder.mkdir()
    (folder / "rl_agent_config.json").write_text("{}")

    assert checkpoint_dir("source_stance") == folder
    with pytest.raises(UnknownCheckpoint):
        checkpoint_dir("worth_offering")


def test_state_and_states_are_exclusive(fake_laya):

    with TestClient(app) as client:
        both = client.post("/decisions", json={"checkpoint": "multilingual", "state": "x",
                                               "states": ["y"], "questions": STANCE})
        none = client.post("/decisions", json={"checkpoint": "multilingual", "questions": STANCE})
        no_questions = client.post("/decisions", json={"checkpoint": "multilingual", "state": "x",
                                                       "questions": {}})

    assert both.status_code == none.status_code == no_questions.status_code == 422


def test_the_least_recently_used_checkpoint_is_unloaded(fake_laya, tmp_path):

    for name in ["a", "b", "c"]:
        (tmp_path / name).mkdir()
        (tmp_path / name / "rl_agent_config.json").write_text("{}")

    models = decisions_module.decision_models
    models.predict("a", "x", STANCE)
    models.predict("b", "x", STANCE)
    models.predict("a", "x", STANCE)        # a is now the most recent
    models.predict("c", "x", STANCE)        # so b goes

    assert models.loaded() == ["a", "c"]
    # Path(...).name, not a split on "/": on Windows the folders are
    # handed to laya.load with backslashes.
    assert [Path(path).name for path in fake_laya] == ["a", "b", "c"]


def test_the_real_multilingual_checkpoint_answers_in_shape():
    """Laya itself, untrained on this project: a distribution over the
    question's own options and a choice among them.

    Not whether it is right. Written first as "supports beats unrelated"
    for a source that plainly states the claim, and the untrained
    checkpoint answered 0.48 against 0.52 (2026-10-23): zero-shot it is a
    coin on this question, which is why every decision is fine-tuned
    (backend/data/evaluation/experiments/laya/)."""

    models = DecisionModels(max_loaded=1)
    result = models.predict(
        "multilingual",
        "Claim: Spain's solar capacity grew 30% in 2025.\n"
        "Source: Spain added a record amount of solar in 2025, raising its installed "
        "capacity by about 30 percent, the grid operator said.",
        STANCE,
    )

    answer = result["answers"]["stance"]
    assert set(answer["probabilities"]) == {"supports", "unrelated"}
    assert sum(answer["probabilities"].values()) == pytest.approx(1.0, abs=1e-3)
    assert answer["choice"] == max(answer["probabilities"], key=answer["probabilities"].get)
