"""
A claim restated as something that can be checked on its own.

Claims are extracted one sentence at a time, and a news sentence leans on
its article: "Samuda argued Jamaica was different because, although the
country had 'conquered our crime monster', it had 'spent 30 years being in
the top three most murderous countries on the planet'". Searched as it
stood that became `Samuda Jamaica "30"`, and the verifier was asked
whether a quotation was true. Two things in it can be checked - that a
minister said it, and that Jamaica spent thirty years among the three
highest murder rates - and only the second is the fact the article rests
on.

One model call per claim turns the sentence into:

- `standalone`: the sentence made self-contained, from the headline and
  the opening alone (who "Samuda" is, which country, when);
- `checkable`: the proposition to verify - for reported speech, the fact
  inside the quote, without "argued" or "said";
- `kind`, `speaker` and one or two `questions`, for the person reading
  the verdict.

`checkable` is then what is searched, ranked and judged. The answer is
held to the sentence the way the writer is held to its sources
(writer/draft_checks.py): no figure that is in neither the sentence nor
the article's headline and opening, nothing that shares no word with the
sentence, nothing empty or sprawling. A refused answer, an opinion, a
model that is down or a claim with a deadline: the sentence is checked as
written, and `ClaimRestatement.note` says why. Never a reason to fail a
claim.

Off unless `claim_restatement` says `standalone` (settings.py).
"""

from __future__ import annotations

import re
from logging import getLogger
from typing import TYPE_CHECKING

from src.config.lexicons import lexicon_for
from src.config.settings import settings
from src.models.core.claim import Claim, ClaimFacts
from src.models.fact_checker.restatement import ClaimRestatement
from src.services.fact_checker.terms import TOKEN, content_terms, fold
from src.services.llms import LLMClient, LLMUnavailableError

if TYPE_CHECKING:
    from src.services.fact_checker.claim_selector import ArticleContext

logger = getLogger(__name__)

# The opening the model is shown. The lead is what names who and where.
LEAD_CHARS = 700

# How much of the article before the sentence the model is shown: enough
# for the two or three sentences that name what "they", "the initiative" or
# "the specialist" refers to.
BEFORE_CHARS = 900

MAX_CHECKABLE = 400
MIN_CHECKABLE = 15
MAX_QUESTIONS = 2

# A restatement that shares fewer of the sentence's content words than this
# has drifted to another claim.
MIN_SHARED_WORDS = 1

NUMBER = re.compile(r"\d+(?:[.,]\d+)*")

# Two or more capitalised words in a row: a name the restatement put back
# ("Matthew Samuda", "Ciudad de México"), which the entity model never saw.
NAME = re.compile(
    r"\b[A-ZÁÉÍÓÚÑÜ][\w'’-]+(?:\s+(?:de|del|la|las|los|of|the|y|and)?\s*[A-ZÁÉÍÓÚÑÜ][\w'’-]+)+"
)

SYSTEM_PROMPT = """You prepare one sentence from a news article for a fact-checker.
The sentence was cut out of its article, so on its own it can be unclear who is speaking and what exactly is claimed.

Use ONLY the article's headline, its opening, the passage just before the sentence and the sentence. Never add a fact, a number, a date or a name that is not in them.
Write in the language of the sentence.

Answer with JSON only:
{"kind": "fact" | "attributed" | "opinion",
 "speaker": "name and role of whoever is quoted or paraphrased, or null",
 "standalone": "the sentence rewritten so it is understood without the article: full names, roles, places and dates from the article; no pronouns",
 "checkable": "the single factual statement a fact-checker should verify",
 "questions": ["one or two questions a fact-checker would search to settle it"]}

Pronouns and vague references: if the sentence refers back to something named earlier - a pronoun or a verb with no subject ("they have", "tienen", "it", "esto"), or a phrase like "the initiative", "the programme", "the model", "the specialist", "la iniciativa", "el investigador" - put the NAME back from the passage before it (the project's name, the person's full name and role, the place). A search for "the initiative" finds nothing; a search for the project's name does. Never guess a name the text does not give.

Rules for "checkable":
- A plain statement that can be true or false. Never a question, never a topic.
- Keep EVERY number and date of the sentence.
- "fact": the sentence's own assertion, made self-contained.
- "attributed" (someone says, argues, claims, warns...): the fact INSIDE what they say, stated plainly, without "said" or "argued". Not whether they said it.
- "opinion" (a judgement, a demand, a hope, what should happen): repeat the sentence.

Example. Headline: "Lisbon's mayor defends the green plan". Sentence: "Moedas said the city had planted 12,000 trees since 2020, more than any other capital."
{"kind": "attributed", "speaker": "Carlos Moedas, mayor of Lisbon",
 "standalone": "Carlos Moedas, mayor of Lisbon, said Lisbon had planted 12,000 trees since 2020, more than any other European capital.",
 "checkable": "Lisbon has planted 12,000 trees since 2020, more than any other European capital.",
 "questions": ["How many trees has Lisbon planted since 2020?", "Which European capital planted the most trees since 2020?"]}"""


class ClaimRestater:

    def __init__(self, client: LLMClient | None = None):

        self.client = client

    def restate(
        self,
        claim: Claim,
        context: ArticleContext | None,
        language: str | None = None,
    ) -> ClaimRestatement:

        if context is None or not (context.title or context.lead):
            return _as_written(claim, "No article to read it in: checked as written.")

        client = self.client or LLMClient(model=settings.RESTATEMENT_LLM_MODEL)

        user_prompt = (
            f"Headline: {context.title}\n"
            f"Opening: {context.lead[:LEAD_CHARS]}\n\n"
            f"{before_block(context, claim.text)}"
            f"Sentence: {claim.text}"
        )

        try:
            answer = client.complete_json(SYSTEM_PROMPT, user_prompt, max_tokens=400)
        except LLMUnavailableError:
            return _as_written(claim, "The model could not be reached: checked as written.")
        except Exception:
            logger.warning("Restating a claim failed", exc_info=True)
            return _as_written(claim, "Restating failed: checked as written.")

        return validate(answer, claim, context, language)


def passage_before(context: ArticleContext, sentence: str) -> str:
    """The article's text just before `sentence`, or "" when it is not found in the body."""

    body = context.body or ""
    at = body.find(sentence)

    if at <= 0:
        # The harness may hold the sentence in slightly different spacing.
        at = body.find(" ".join(sentence.split())[:60]) if sentence else -1

    if at <= 0:
        return ""

    return body[max(0, at - BEFORE_CHARS):at].strip()


def before_block(context: ArticleContext, sentence: str) -> str:

    before = passage_before(context, sentence)

    return f"Passage just before the sentence: {before}\n\n" if before else ""


def validate(
    answer: dict | None,
    claim: Claim,
    context: ArticleContext,
    language: str | None = None,
) -> ClaimRestatement:
    """The model's answer, held to the sentence and its article - or the sentence as written, with why."""

    if not isinstance(answer, dict):
        return _as_written(claim, "The model gave no usable answer: checked as written.")

    kind = answer.get("kind") if answer.get("kind") in ("fact", "attributed", "opinion") else "fact"
    checkable = _text(answer.get("checkable"))
    standalone = _text(answer.get("standalone")) or checkable
    speaker = _text(answer.get("speaker")) or None
    questions = [_text(question) for question in answer.get("questions") or [] if _text(question)][:MAX_QUESTIONS]

    restatement = ClaimRestatement(
        kind=kind,
        speaker=speaker,
        standalone=standalone,
        checkable=checkable,
        questions=questions,
    )

    # A sentence that carries a figure has something to check, whatever
    # the model calls it: the 3B called "it had spent 30 years being in the
    # top three most murderous countries" an opinion (2026-11-03).
    if kind == "opinion" and _numbers(claim.text):
        kind = "attributed" if speaker else "fact"
        restatement = restatement.model_copy(update={"kind": kind})

    if kind == "opinion":
        return _refused(restatement, claim, "An opinion, with nothing factual to check: checked as written.")

    # Nothing the article does not say. A figure the model wrote is the
    # one thing a search would then look for verbatim.
    known = _numbers(" ".join([claim.text, context.title, context.lead, passage_before(context, claim.text)]))
    invented = sorted(_numbers(f"{checkable} {standalone}") - known)

    if invented:
        return _refused(restatement, claim, f"The restatement added {', '.join(invented)}, which the article does not say: checked as written.")

    # The checkable statement first; when the model got that wrong - a
    # question, a topic, a figure dropped (all three seen from the 3B on
    # 2026-11-03: "Jamaica's ranking in the most murderous countries on the
    # planet" for a sentence about thirty years in the top three) - its own
    # standalone sentence, held to the same rules, is the next best thing.
    problems = _problems(checkable, claim, language)

    if not problems:
        return restatement

    if standalone and standalone != checkable and not _problems(standalone, claim, language):
        return restatement.model_copy(update={
            "checkable": standalone,
            "note": f"Its checkable statement {problems[0]}: checked as its standalone sentence.",
        })

    return _refused(restatement, claim, f"The restatement {problems[0]}: checked as written.")


def _problems(statement: str, claim: Claim, language: str | None) -> list[str]:
    """Why `statement` cannot stand in for the sentence, if it cannot - in words a person reads in the note."""

    problems = []

    if not MIN_CHECKABLE <= len(statement) <= MAX_CHECKABLE:
        problems.append("was empty or too long")

    if statement.rstrip().endswith("?") or statement.lstrip().startswith("¿"):
        problems.append("was a question, not a statement")

    dropped = sorted(_numbers(claim.text) - _numbers(statement))
    if dropped:
        problems.append(f"dropped {', '.join(dropped)} from the sentence")

    sentence = {fold(word) for word in content_terms(claim.text, language)}
    shared = sentence & {fold(word) for word in content_terms(statement, language)}

    if sentence and len(shared) < MIN_SHARED_WORDS:
        problems.append("shared no word with the sentence")

    return problems


def working_claim(claim: Claim, restatement: ClaimRestatement) -> Claim:
    """
    The claim the stages after this one search and judge: the checkable
    statement, with the sentence's entities, figures and dates that it
    still mentions - and the names it put back - so the anchor query asks
    for what the restatement is about, not for who said it.
    """

    if not restatement.used:
        return claim

    text = restatement.checkable
    folded = fold(text)

    entities = {
        label: [value for value in values if fold(value) in folded]
        for label, values in claim.entities.items()
    }

    known = {fold(value) for values in entities.values() for value in values}
    names = []

    for found in NAME.findall(text):

        # A sentence's first word is capitalised whatever it is: "Since
        # October ..." is not a name, "October" alone is not one either.
        words = found.split()
        while words and fold(words[0]) in _NOT_A_NAME:
            words = words[1:]
        while words and fold(words[-1]) in _NOT_A_NAME:
            words = words[:-1]

        name = " ".join(words)

        if len(words) >= 2 and fold(name) not in known:
            names.append(name)

    entities = {label: values for label, values in entities.items() if values}
    if names:
        entities["RESTATED"] = list(dict.fromkeys(names))

    tokens = set(TOKEN.findall(folded))

    def kept(values: list[str]) -> list[str]:
        return [value for value in values if all(token in tokens for token in TOKEN.findall(fold(value)))]

    facts = ClaimFacts(
        figures=kept(claim.facts.figures),
        dates=kept(claim.facts.dates),
        quotes=[],
    )

    return claim.model_copy(update={"text": text, "entities": entities, "facts": facts, "written_as": claim.text})


# ----------------------------------------------------------------------


# Capitalised for other reasons than being a name: a sentence's first word,
# a month, a weekday. Stripped from the edges of a run before it counts.
_NOT_A_NAME = {fold(word) for language in ("en", "es") for word in lexicon_for(language).stopwords} | {
    "since", "after", "before", "although", "while", "when", "desde", "tras", "aunque", "cuando",
    "january", "february", "march", "april", "may", "june", "july", "august", "september",
    "october", "november", "december", "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
    "septiembre", "octubre", "noviembre", "diciembre", "lunes", "martes", "miercoles", "jueves",
    "viernes", "sabado", "domingo",
}


def _text(value) -> str:
    return " ".join(str(value).split()) if isinstance(value, str) else ""


def _numbers(text: str) -> set[str]:
    return {number.replace(",", ".").rstrip(".") for number in NUMBER.findall(text)}


def _as_written(claim: Claim, note: str) -> ClaimRestatement:
    return ClaimRestatement(standalone=claim.text, checkable=claim.text, used=False, note=note)


def _refused(restatement: ClaimRestatement, claim: Claim, note: str) -> ClaimRestatement:
    """The model's reading is kept for the person to see; the sentence is what gets checked."""

    return restatement.model_copy(update={"checkable": claim.text, "used": False, "note": note})
