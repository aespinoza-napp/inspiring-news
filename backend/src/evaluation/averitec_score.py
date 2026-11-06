"""
AVeriTeC's evidence score: a run's questions and answers against the
annotators', by Hungarian-matched METEOR (Schlichtkrull et al. 2023).

A re-implementation of the official `eval.py` (github.com/MichSchli/AVeriTeC),
read on 2026-11-06, so a run can be scored on dev without the shared task's
server. What it follows:

- METEOR between every predicted and every gold string (nltk's
  `single_meteor_score` over `word_tokenize`d text), then the one-to-one
  assignment that maximises the total, divided by the number of gold strings:
  a run that asks fewer questions than the annotators loses the rest.
- At most 10 predicted questions. A gold question with no answer reads "No
  answer could be found."; a Boolean answer has its explanation appended.
- Q-only compares questions; Q+A compares "question answer" strings.
- The AVeriTeC score at a level counts a claim right only when its verdict is
  right AND its Q+A score exceeds the level; 0.25 is the one the shared task
  ranked by.

Where it may differ: the assignment is found by exhaustive search over the
smaller side (exact, and small here: this pipeline asks at most three), not
scipy's `linear_sum_assignment`; tokenisation is nltk's, as the official
script's; the official file's own handling of several answers to one
question is followed as the summary of it read, not line by line. Read its
figures as this re-implementation's, and say so beside any published one.

A run without questions (the sentence and checkable plans) scores 0 on all
three by construction: reported as "no questions", never as a result.
"""

from __future__ import annotations

import json
from functools import lru_cache
from itertools import permutations
from pathlib import Path

from src.models.fact_checker.questions import NO_ANSWER

MAX_QUESTIONS = 10

LEVELS = (0.1, 0.2, 0.25, 0.3, 0.4, 0.5)

RANKED_LEVEL = 0.25

# Past this many on the smaller side, exhaustive assignment is too slow.
MAX_EXACT = 7

DEFAULT_GOLD = Path("data/evaluation/averitec/raw/dev.json")


@lru_cache(maxsize=None)
def _tokens(text: str) -> tuple[str, ...]:

    from nltk import word_tokenize

    return tuple(word_tokenize(text))


@lru_cache(maxsize=None)
def meteor(candidate: str, reference: str) -> float:

    from nltk.translate.meteor_score import single_meteor_score

    return float(single_meteor_score(list(_tokens(reference)), list(_tokens(candidate))))


def assignment_utility(predicted: list[str], gold: list[str]) -> float:
    """The best one-to-one total METEOR, over the number of gold strings."""

    if not predicted or not gold:
        return 0.0

    scores = [[meteor(p, g) for g in gold] for p in predicted]

    rows, columns = len(predicted), len(gold)

    if min(rows, columns) > MAX_EXACT:
        raise ValueError(f"{rows} x {columns}: too large for the exhaustive assignment")

    if rows <= columns:
        best = max(
            sum(scores[row][column] for row, column in zip(range(rows), chosen))
            for chosen in permutations(range(columns), rows)
        )
    else:
        best = max(
            sum(scores[row][column] for row, column in zip(chosen, range(columns)))
            for chosen in permutations(range(rows), columns)
        )

    return best / columns


def gold_strings(example: dict) -> tuple[list[str], list[str]]:
    """The annotators' questions, and their "question answer" strings."""

    questions, full = [], []

    for item in example.get("questions") or []:

        question = (item.get("question") or "").strip()
        answers = []

        for answer in item.get("answers") or []:
            text = (answer.get("answer") or "").strip()
            if answer.get("answer_type") == "Boolean" and answer.get("boolean_explanation"):
                text = f"{text}. {answer['boolean_explanation'].strip()}"
            if text:
                answers.append(text)

        questions.append(question)
        full.append(f"{question} {' '.join(answers) or NO_ANSWER}")

    return questions, full


def predicted_strings(record: dict) -> tuple[list[str], list[str]]:
    """A record's kept questions, and their "question answer" strings."""

    plan = record.get("questionPlan") or {}

    if not plan.get("used"):
        return [], []

    kept = [item for item in plan.get("questions") or [] if item.get("kept")][:MAX_QUESTIONS]

    return (
        [item["text"] for item in kept],
        [f"{item['text']} {item.get('answer') or NO_ANSWER}" for item in kept],
    )


def gold_index(record_id: str) -> int:
    """`averitec-dev-0243` is the 244th claim of dev.json."""

    return int(record_id.rsplit("-", 1)[1])


def load_gold(path: Path = DEFAULT_GOLD) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def score_record(record: dict, example: dict, correct: bool) -> dict:

    gold_q, gold_qa = gold_strings(example)
    pred_q, pred_qa = predicted_strings(record)

    q_only = assignment_utility(pred_q, gold_q)
    qa = assignment_utility(pred_qa, gold_qa)

    return {
        "id": record.get("id"),
        "questions": len(pred_q),
        "goldQuestions": len(gold_q),
        "qOnly": round(q_only, 4),
        "qa": round(qa, 4),
        "correct": correct,
        "levels": {str(level): bool(correct and qa > level) for level in LEVELS},
    }


def evaluate(records: list[dict], gold: list[dict]) -> dict:
    """
    Q-only, Q+A and the AVeriTeC score at every level, over `records`. A claim
    with no verdict is wrong, as in the accuracy beside it.
    """

    from src.evaluation.averitec import _gold, predicted_class

    per_claim = []

    for record in sorted(records, key=lambda item: item.get("id") or ""):

        example = gold[gold_index(record["id"])]
        correct = predicted_class(record) is not None and predicted_class(record) == _gold(record)

        per_claim.append(score_record(record, example, correct))

    count = len(per_claim)

    def mean(values) -> float | None:
        values = list(values)
        return round(sum(values) / len(values), 4) if values else None

    with_questions = sum(1 for item in per_claim if item["questions"])

    return {
        "claims": count,
        "claimsWithQuestions": with_questions,
        "noQuestions": with_questions == 0,
        "questionsPerClaim": mean(item["questions"] for item in per_claim),
        "goldQuestionsPerClaim": mean(item["goldQuestions"] for item in per_claim),
        "accuracy": mean(1.0 if item["correct"] else 0.0 for item in per_claim),
        "qOnly": mean(item["qOnly"] for item in per_claim),
        "qa": mean(item["qa"] for item in per_claim),
        "averitecScore": {
            str(level): mean(1.0 if item["levels"][str(level)] else 0.0 for item in per_claim)
            for level in LEVELS
        },
        "rankedLevel": RANKED_LEVEL,
        "perClaim": per_claim,
    }


def render(result: dict) -> list[str]:

    if result["noQuestions"]:
        return [
            f"No questions in this run ({result['claims']} claims): Q-only, Q+A and the "
            "AVeriTeC score are 0 by construction, not a result.",
        ]

    levels = " | ".join(f"{level}: {value:.3f}" for level, value in result["averitecScore"].items())

    return [
        f"Claims: {result['claims']}, with questions: {result['claimsWithQuestions']} "
        f"({result['questionsPerClaim']} per claim; the annotators wrote {result['goldQuestionsPerClaim']}).",
        f"Accuracy: {result['accuracy']:.3f}. Q-only: {result['qOnly']:.3f}. Q+A: {result['qa']:.3f}.",
        f"AVeriTeC score at {RANKED_LEVEL}: {result['averitecScore'][str(RANKED_LEVEL)]:.3f}.",
        f"By level: {levels}.",
        "This re-implementation of the official scorer (averitec_score.py), against the gold file given.",
    ]
