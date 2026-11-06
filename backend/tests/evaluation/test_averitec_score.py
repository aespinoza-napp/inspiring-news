"""AVeriTeC's evidence score, re-implemented: Hungarian METEOR over questions and answers."""

import pytest

pytest.importorskip("nltk")

from src.evaluation import averitec, averitec_score
from src.models.fact_checker.questions import NO_ANSWER


def _needs_nltk_data():
    try:
        averitec_score.meteor("a cat sat", "a cat sat")
    except LookupError:
        pytest.skip("nltk's wordnet and punkt_tab are not downloaded")


GOLD = {
    "questions": [
        {"question": "Where was the claim first published?", "answers": [{"answer": "On Facebook", "answer_type": "Extractive"}]},
        {"question": "Did WHO say millets prevent COVID-19?", "answers": [{"answer": "No", "answer_type": "Boolean", "boolean_explanation": "WHO lists no food that prevents it"}]},
        {"question": "Is there any evidence?", "answers": []},
    ],
}


def record(questions, verdict="FALSE", used=True):
    return {
        "id": "averitec-dev-0000",
        "verdict": verdict,
        "label": "FALSE",
        "labelRaw": "Refuted",
        "questionPlan": {
            "used": used,
            "questions": [{"text": q, "kept": True, "answer": a} for q, a in questions],
        },
    }


def test_gold_strings_follow_the_official_script():

    questions, full = averitec_score.gold_strings(GOLD)

    assert questions[0] == "Where was the claim first published?"
    assert full[1] == "Did WHO say millets prevent COVID-19? No. WHO lists no food that prevents it"
    assert full[2] == f"Is there any evidence? {NO_ANSWER}"


def test_the_assignment_is_one_to_one_and_divided_by_the_gold_count():

    _needs_nltk_data()

    same = averitec_score.assignment_utility(["Where was the claim first published?"], ["Where was the claim first published?"] * 3)

    # One perfect match out of three gold questions: a third at most.
    assert same == pytest.approx(averitec_score.meteor("Where was the claim first published?", "Where was the claim first published?") / 3)
    assert averitec_score.assignment_utility([], ["anything"]) == 0.0


def test_a_claim_counts_only_with_its_evidence_above_the_level():

    _needs_nltk_data()

    good = record([("Did WHO say millets prevent COVID-19?", "No. WHO lists no food that prevents it")])
    scored = averitec_score.score_record(good, GOLD, correct=True)

    assert scored["qa"] > 0
    assert scored["levels"]["0.1"] == (scored["qa"] > 0.1)

    wrong = averitec_score.score_record(good, GOLD, correct=False)
    assert not any(wrong["levels"].values())


def test_a_run_without_questions_scores_nothing_by_construction():

    _needs_nltk_data()

    result = averitec_score.evaluate([record([], used=False)], [GOLD])

    assert result["noQuestions"] and result["qOnly"] == 0.0
    assert "by construction" in averitec_score.render(result)[0]


def test_the_submission_carries_the_kept_questions():

    [entry] = averitec.submission([record([("Where was it published?", "On Facebook")])])

    assert entry["questions"] == [{"question": "Where was it published?", "answers": [{"answer": "On Facebook", "answer_type": "Extractive"}]}]
    assert averitec.submission([record([("Q?", "A")], used=False)])[0]["questions"] == []
