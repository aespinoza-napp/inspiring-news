from typing import Literal

from pydantic import BaseModel, Field


class ClaimRestatement(BaseModel):
    """
    What a claim was checked *as* (services/fact_checker/restatement.py):
    the sentence rewritten so it can be searched and judged on its own.
    Kept beside the check so a reader of the verdict can see what exactly
    was verified, not only the sentence it came from.
    """

    # "fact": the sentence asserts something checkable itself.
    # "attributed": someone is reported saying it; what is checked is the
    #   fact inside the quote, not whether they said it.
    # "opinion": nothing factual to check; searched as written.
    kind: Literal["fact", "attributed", "opinion"] = "fact"

    # Who is speaking, for "attributed": name and role, from the article.
    speaker: str | None = None

    # The sentence made self-contained: names in full, pronouns and
    # "the minister" resolved, the article's place and date put back.
    standalone: str = ""

    # The proposition that was searched and judged.
    checkable: str = ""

    # What a fact-checker would ask to settle it: shown, not searched.
    questions: list[str] = Field(default_factory=list)

    # False when the model's answer was refused (an invented figure, a
    # drift away from the sentence, no answer at all) and the sentence was
    # checked as written. `note` says why.
    used: bool = True

    note: str | None = None
