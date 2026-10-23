"""
The Laya decisions' data and scoring (src/evaluation/decisions.py).

The splits are the rule's (data/evaluation/experiments/laya/rule.md):
these tests hold what makes a test set a test set - nothing of it in
training - and the scorer to values worked out by hand.
"""

import json

import pytest

from src.config.decisions import DECISIONS
from src.evaluation import decisions


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("laya")
    counts = decisions.build(out)

    def read(name):
        return [json.loads(line) for line in (out / name).read_text(encoding="utf-8").splitlines()]

    return counts, read


def test_every_decision_has_a_train_and_a_test_set(built):

    counts, _ = built

    for name, count in counts.items():
        assert count["train"] > 0 and count["test"] > 0, name


def test_no_test_candidate_is_trained_on(built):

    _, read = built
    test_keys = {decisions.article_key(line["meta"]["id"]) for line in read("worth_offering_test.jsonl")}
    trained, ranking = decisions.labelled_candidates()
    trained_keys = {decisions.article_key(c["url"]) for c in trained}

    assert not trained_keys & test_keys
    assert len(test_keys) == len(ranking)


def test_checkable_claims_split_by_the_batch_day(built):

    _, read = built
    test = read("checkable_claim_test.jsonl")

    assert all(line["meta"]["id"][:10] >= decisions.CHECKABLE_TEST_FROM for line in test)
    assert all("meta" not in line for line in read("checkable_claim_train.jsonl"))


def test_the_questions_are_the_configured_ones(built):

    _, read = built

    for name in ("worth_offering", "topic_group", "checkable_claim"):
        line = read(f"{name}_train.jsonl")[0]
        assert line["questions"] == {name: DECISIONS[name]}


def test_a_story_in_several_groups_splits_its_target_evenly(built):

    _, read = built

    for line in read("topic_group_train.jsonl"):
        probabilities = line["gold"]["topic_group"]["probabilities"]
        assert sum(probabilities.values()) == pytest.approx(1.0)
        assert len({p for p in probabilities.values() if p > 0}) == 1


def _predictions(tmp_path, decision, rows):
    path = tmp_path / "p.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return decisions.score(decision, path)


def test_topic_group_accuracy_is_paired_against_the_classifier(tmp_path):

    rows = [
        {"meta": {"classifier": "science"}, "expected": {"topic_group": "science"},
         "answers": {"topic_group": {"choice": "science"}}},
        {"meta": {"classifier": "health"}, "expected": {"topic_group": "science"},
         "answers": {"topic_group": {"choice": "science"}}},
        {"meta": {"classifier": "culture"}, "expected": {"topic_group": "culture"},
         "answers": {"topic_group": {"choice": "society"}}},
        {"meta": {"classifier": "society"}, "expected": {"topic_group": "society"},
         "answers": {"topic_group": {"choice": "society"}}},
    ]

    result = _predictions(tmp_path, "topic_group", rows)

    assert result["primary"]["comparator"] == 0.75
    assert result["primary"]["laya"] == 0.75
    assert result["primary"]["difference"] == 0.0


def test_a_perfect_ranking_beats_a_reversed_one_and_is_adopted(tmp_path):

    rows = []
    for i, kept in enumerate([True] * 20 + [False] * 20):
        rows.append({"meta": {"selectorScore": -i}, "expected": {"checkable_claim": kept},
                     "answers": {"checkable_claim": {"noul": 1.0 - i / 40}}})

    result = _predictions(tmp_path, "checkable_claim", rows)

    # The selector scores every kept claim *above* every skipped one too
    # (-0..-19 against -20..-39): both are perfect, so nothing is adopted.
    assert result["primary"]["comparator"] == 1.0
    assert result["primary"]["laya"] == 1.0
    assert result["adopted"] is False

    for row in rows:
        row["meta"]["selectorScore"] = -row["meta"]["selectorScore"]

    result = _predictions(tmp_path, "checkable_claim", rows)

    assert result["primary"]["comparator"] == 0.0
    assert result["primary"]["low"] > 0
    assert result["adopted"] is True


def test_mcnemar_is_exact_on_the_discordant_pairs():

    assert decisions._mcnemar(6, 6) == 1.0
    assert decisions._mcnemar(0, 6) == pytest.approx(2 / 64)
    assert decisions._mcnemar(0, 0) == 1.0


def test_the_topic_comparison_counts_who_is_right_alone(tmp_path):

    def line(key, gold, classifier, choice, p):
        return {"meta": {"id": key, "language": "en", "classifier": classifier},
                "expected": {"topic_group": gold},
                "answers": {"topic_group": {"choice": choice, "probabilities": {choice: p}}}}

    finetuned = [line("a", "science", "science", "science", 0.9),
                 line("b", "health", "science", "health", 0.95),
                 line("c", "society", "society", "culture", 0.6)]
    zero_shot = [line(row["meta"]["id"], row["expected"]["topic_group"], row["meta"]["classifier"], "science", 0.5)
                 for row in finetuned]
    paths = []
    for name, rows in (("zs", zero_shot), ("ft", finetuned)):
        path = tmp_path / f"{name}.jsonl"
        path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
        paths.append(path)

    result = decisions.compare_topic_groups(*paths)

    assert result["accuracy"]["bge-m3"]["right"] == 2
    assert result["accuracy"]["laya fine-tuned"]["right"] == 2
    assert result["accuracy"]["laya zero-shot"]["right"] == 1
    agreement = result["agreement"]
    assert (agreement["bothRight"], agreement["onlyBgeM3"], agreement["onlyLaya"], agreement["eitherRight"]) == (1, 1, 1, 3)
    # Laya's group where they disagree and it is at least 0.9 sure: b is
    # taken (right), c is not (the classifier's, right).
    assert result["combination"]["0.9"] == 3
