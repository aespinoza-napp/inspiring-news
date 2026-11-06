from pydantic import BaseModel, Field


# What AVeriTeC's annotators write when no source answers a question; a
# question the search found nothing for is scored with the same words.
NO_ANSWER = "No answer could be found."


class PlannedQuestion(BaseModel):
    """
    One question the claim was searched by (services/fact_checker/questions.py),
    with the detail of the checkable point it carries and, after the verdict,
    what the sources its query found answered.
    """

    text: str

    # The decisive detail of the claim it asks about: a figure, an
    # identifier, a date, a name - else a term.
    detail: str = ""

    # The query it was searched as, and the tag its hits carry in
    # `Evidence.found_by` ("question-1"), which is how its answer is found.
    query: str = ""

    tag: str = ""

    # False when the checks refused it; `reason` says why.
    kept: bool = True

    reason: str | None = None

    # The passage of the first judged source its query found, else NO_ANSWER.
    answer: str | None = None

    answer_url: str | None = None


class QuestionPlan(BaseModel):
    """
    `query_plan: questions`: what a claim was searched by. `used` is False when
    no question survived the checks (or none could be asked) and the claim was
    searched by the checkable plan; `note` says why.
    """

    questions: list[PlannedQuestion] = Field(default_factory=list)

    used: bool = True

    note: str | None = None

    @property
    def kept(self) -> list[PlannedQuestion]:
        return [question for question in self.questions if question.kept]
