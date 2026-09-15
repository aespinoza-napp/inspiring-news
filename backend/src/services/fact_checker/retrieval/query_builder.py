"""
Turns a claim into the queries that actually retrieve evidence for it.

The whole claim sentence used to be the query. That is a poor web search
for two reasons, both of which cost real recall:

1. Claims are extracted per sentence, so anaphora is unresolved. "La
   compañía anunció que reducirá sus emisiones un 40%" reaches the search
   engine with no way to know which company - the antecedent was in the
   previous sentence, which the extractor never sees.
2. A long sentence is matched as a bag of words, and its discriminative
   terms (the figure, the year, the organisation) are diluted by the
   prose around them.

So a query is built from the parts that identify the event - entities,
figures, dates - with the article's own subject restored when the claim
does not name one itself.
"""

from __future__ import annotations

import re

from src.models.core.claim import Claim
from src.services.fact_checker.claim_selector import ArticleContext

WORD = re.compile(r"\b[^\W\d_]{4,}\b", re.UNICODE)

# Terms that pull refutations to the surface, per language. Every query
# built from a claim is phrased affirmatively, which biases retrieval
# toward documents that agree with it - so the affirmative query alone
# can only ever confirm. These are what give a contradiction a chance of
# being retrieved at all.
REFUTATION_TERMS = {
    "en": "fact check OR debunked OR false",
    "es": "verificación OR desmentido OR bulo OR falso",
}

MAX_ENTITIES = 4
MAX_FIGURES = 2
MAX_DATES = 1
MAX_FALLBACK_WORDS = 8


def _entities(claim: Claim) -> list[str]:

    return [
        value
        for values in claim.entities.values()
        for value in values
        if value.strip()
    ][:MAX_ENTITIES]


def _quoted(term: str) -> str:
    """
    Figures are quoted so they are matched verbatim. Unquoted, "40" is
    just a common token and the engine is free to ignore it - which
    discards the single most checkable part of the claim.
    """

    return f'"{term.strip()}"'


def build_query(claim: Claim, context: ArticleContext | None = None) -> str:
    """The affirmative query: what identifies this claim's event."""

    parts: list[str] = []

    entities = _entities(claim)

    parts += entities

    parts += [_quoted(figure) for figure in claim.facts.figures[:MAX_FIGURES]]

    parts += claim.facts.dates[:MAX_DATES]

    # No entity in the sentence means the subject is elsewhere in the
    # article - almost always a pronoun referring back to the headline's
    # subject. The title is the cheapest available antecedent.
    if not entities and context and context.title:
        parts.append(context.title)

    # Nothing identifying at all: fall back to the claim's longer words,
    # which is still better than the raw sentence with its stopwords.
    if not parts:
        parts = WORD.findall(claim.text)[:MAX_FALLBACK_WORDS]

    return " ".join(part.strip() for part in parts if part.strip())


def build_refutation_query(
    claim: Claim,
    context: ArticleContext | None = None,
    language: str | None = None,
) -> str:
    """The same event, asked in a way that can surface a contradiction."""

    base = build_query(claim, context)

    if not base:
        return ""

    terms = REFUTATION_TERMS.get(
        (language or "en").lower()[:2],
        REFUTATION_TERMS["en"],
    )

    return f"{base} {terms}"
