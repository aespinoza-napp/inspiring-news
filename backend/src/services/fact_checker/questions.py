"""
The questions a claim is searched by (`query_plan: questions`, 2026-11-06).

A fact-checker decides what would settle a claim before searching, and
AVeriTeC's leading systems do the same: InFact asks ten questions and
searches each, HerO has an 8B model write them (the thesis, "Deciding What
to Search"). On 20 train claims of the custom set the pipeline's queries
carried neither the decisive figure nor the kind of source that would hold
it (docs/troubleshooting/fact-checking/01-what-to-look-for.md).

One model call writes up to three questions from the claim and the details
of its checkable point (retrieval/checkable.py). The model is shown the
claim's text alone - no speaker, place or date, as in every AVeriTeC
condition - and its answer is held to the claim without a model, the way a
restatement is (restatement.py). A question is refused when it:

- states a figure the claim does not;
- does not carry the claim's subject: a name or subject word of the point,
  else one of its first terms, as the anchor query takes them;
- carries no decisive detail: a figure, identifier, date or name of the
  point, else one of its terms;
- repeats a question already kept: the same detail, in mostly its words.

Pieces cut too small lose the context that makes them checkable (Gunjal
and Durrett's molecular facts; the dengue claim that never names dengue):
carrying the subject is what keeps each question about this claim.

Each kept question is one search (query_builder.question_query), so a claim
is still three searches. Its answer is the passage of the first judged
source that its query found, with no second call: what AVeriTeC's scorer
compares with the annotators' answers. No question kept, the model down or
a deadline: the checkable plan as it is, and `QuestionPlan.note` says why.
Never a reason to fail a claim.

The rule this is measured by, written before it ran:
data/evaluation/experiments/averitec/questions-rule.md.
"""

from __future__ import annotations

import re
from logging import getLogger
from typing import TYPE_CHECKING

from src.models.core.claim import Claim
from src.models.fact_checker.evidence import Evidence, EvidenceStance
from src.models.fact_checker.questions import NO_ANSWER, PlannedQuestion, QuestionPlan
from src.services.fact_checker.retrieval.checkable import CheckablePoint, carries, is_proper, names_in, point_for_thresholds, proper_names
from src.services.fact_checker.retrieval.query_builder import MAX_QUESTIONS, question_query, question_tag
from src.services.fact_checker.terms import content_terms, fold
from src.services.llms import LLMClient, LLMUnavailableError

if TYPE_CHECKING:
    from src.services.fact_checker.claim_selector import ArticleContext

logger = getLogger(__name__)

MIN_QUESTION_CHARS = 12
MAX_QUESTION_CHARS = 220

# A question on the same detail as a kept one, this much inside it, asks the
# same thing again. On another detail it does not: "how many cases in 2026"
# and "did it report 212" share most of their words and ask different things.
REPEAT_OVERLAP = 0.8

# The stances that answer a question: the source said something on its point.
ANSWERING = (EvidenceStance.SUPPORTS, EvidenceStance.CONTRADICTS)

# What an answer is cut to: AVeriTeC's answers are a sentence or two.
MAX_ANSWER_CHARS = 400

NUMBER = re.compile(r"\d+(?:[.,]\d+)*")

# The model is told the subject and the details by name. Asked with the
# details alone (6 Nov, first 10 AVeriTeC train claims) the 3B wrote "a
# Presidential candidate" for Joe Biden, and copied the old example's "which
# source counts..." into "What document or study says that...", whose words
# then went into the query.
SYSTEM_PROMPT = """You prepare a claim for a fact-checker: the questions whose answers would show whether it is true.

Rules:
- At most 3 questions, the most decisive first, each about a DIFFERENT detail from the list.
- Every question names the subject given (one of them, when there are several), so it is understood without the claim.
- Ask about the fact itself: what happened, who did it, when, how many, what was said. Never ask which source, document or study says it, and never ask whether the claim is true.
- Never add a number, a date or a name that is not in the claim.
- Write in the language of the claim.

Answer with JSON only: {"questions": ["...", "..."]}

Example. Claim: "Florida has reported 212 travel-related dengue cases so far in 2026."
Subject: Florida
Details: 212; 2026; travel-related dengue cases
{"questions": ["How many travel-related dengue cases has Florida reported in 2026?", "Were the dengue cases Florida reported in 2026 travel-related?"]}

Example. Claim: "Senator John Hale voted against the 2019 farm bill."
Subject: John Hale
Details: 2019; farm bill; voted against
{"questions": ["How did John Hale vote on the 2019 farm bill?", "Which farm bill did John Hale vote against in 2019?"]}"""

class QuestionPlanner:

    def __init__(self, client: LLMClient | None = None):

        self.client = client

    def plan(
        self,
        claim: Claim,
        context: ArticleContext | None = None,
        language: str | None = None,
        thresholds=None,
    ) -> QuestionPlan:

        point = point_for_thresholds(claim, context, language, thresholds)
        subject = subject_of(claim, point)[:3]
        details = [value for value in decisive_details(claim, point) if value not in subject]

        client = self.client or LLMClient()

        user_prompt = (
            f"Claim: {claim.text}\n"
            f"Subject: {'; '.join(subject) or '(none)'}\n"
            f"Details: {'; '.join(details) or '; '.join(subject) or '(none)'}"
        )

        try:
            answer = client.complete_json(SYSTEM_PROMPT, user_prompt, max_tokens=300)
        except LLMUnavailableError:
            return unused("The model could not be reached: searched by the checkable plan.")
        except Exception:
            logger.warning("Planning questions failed", exc_info=True)
            return unused("Planning questions failed: searched by the checkable plan.")

        return validate(answer, claim, point, language)


def unused(note: str) -> QuestionPlan:
    return QuestionPlan(used=False, note=note)


def subject_of(claim: Claim, point: CheckablePoint) -> list[str]:
    """
    What a question has to name, one of them, to be about this claim: its
    names in the sentence's order - else the point's subject words, else its
    first terms. Any one will do: requiring the first refused every question
    on "Nanavati Hospital" for naming it and not "Mumbai", and every one on
    Ryan Zinke for not naming "US" (6 Nov).
    """

    return proper_names(claim, point) or point.subject[:2] or point.terms[:2]


def decisive_details(claim: Claim, point: CheckablePoint) -> list[str]:
    """What a question can turn on: the identifiers, figures, dates and names, else the terms."""

    exact = point.identifiers + point.figures + point.dates + proper_names(claim, point)

    return exact or point.terms


def _carried(text: str, value: str, point: CheckablePoint) -> bool:
    """A figure, identifier or date whole; a name by its core (`names`); a term whole."""

    if value in point.identifiers or value in point.figures or value in point.dates:
        return carries(text, value)

    return names_in(text, value) if is_proper(value) else carries(text, value)


def validate(
    answer: dict | None,
    claim: Claim,
    point: CheckablePoint,
    language: str | None = None,
) -> QuestionPlan:
    """The model's questions, each held to the claim - or the checkable plan, with why."""

    if not isinstance(answer, dict) or not isinstance(answer.get("questions"), list):
        return unused("The model gave no usable questions: searched by the checkable plan.")

    subject = subject_of(claim, point)
    details = decisive_details(claim, point)
    known = _numbers(claim.text)

    questions: list[PlannedQuestion] = []
    kept_words: list[tuple[str, set[str]]] = []

    for raw in answer["questions"]:

        text = " ".join(raw.split()) if isinstance(raw, str) else ""

        if not text:
            continue

        if len(questions) >= 2 * MAX_QUESTIONS:
            break

        # The detail it turns on: another than the subject when it carries one.
        carried = [value for value in details if _carried(text, value, point)]
        detail = next((value for value in carried if value not in subject), carried[0] if carried else "")
        words = {fold(word) for word in content_terms(text, language)}

        reason = None

        if not MIN_QUESTION_CHARS <= len(text) <= MAX_QUESTION_CHARS:
            reason = "empty or too long"
        elif invented := sorted(_numbers(text) - known):
            reason = f"states {', '.join(invented)}, which the claim does not"
        elif subject and not any(_carried(text, value, point) for value in subject):
            reason = "does not name the claim's subject"
        elif not detail:
            reason = "carries none of the claim's decisive details"
        elif any(
            words and same == detail and len(words & kept) / len(words) >= REPEAT_OVERLAP
            for same, kept in kept_words
        ):
            reason = "repeats a kept question"
        elif len(kept_words) >= MAX_QUESTIONS:
            reason = f"past the first {MAX_QUESTIONS}"

        if reason is None:
            kept_words.append((detail, words))

        questions.append(PlannedQuestion(text=text, detail=detail, kept=reason is None, reason=reason))

    position = 0

    for question in questions:
        if question.kept:
            position += 1
            question.query = question_query(question.text, claim, point, language)
            question.tag = question_tag(position)

    if not position:
        return QuestionPlan(
            questions=questions,
            used=False,
            note="No question held to the claim: searched by the checkable plan.",
        )

    return QuestionPlan(questions=questions)


def answered(plan: QuestionPlan, evidence: list[Evidence]) -> QuestionPlan:
    """
    Each kept question with the passage of the first judged source its query
    found that took a side - supports or contradicts: the source's quote when
    the verifier gave one, else its snippet. A source the verifier found
    silent or unrelated answers nothing, and taken first it answered "Did Joe
    Biden fight to cut social security?" with an arXiv abstract on social
    authentication (6 Nov). `evidence` is the check's, in the order it was
    judged.
    """

    if not plan.used:
        return plan

    questions = []

    for question in plan.questions:

        if not question.kept:
            questions.append(question)
            continue

        source = next(
            (item for item in evidence if question.tag in item.found_by and item.stance in ANSWERING),
            None,
        )
        passage = ((source.quote or source.snippet or source.title or "") if source else "").strip()

        questions.append(question.model_copy(update={
            "answer": passage[:MAX_ANSWER_CHARS] if passage else NO_ANSWER,
            "answer_url": source.url if source and passage else None,
        }))

    return plan.model_copy(update={"questions": questions})


def _numbers(text: str) -> set[str]:
    return {number.replace(",", ".").rstrip(".") for number in NUMBER.findall(text)}
