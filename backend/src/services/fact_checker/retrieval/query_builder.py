"""
Turns a claim into the set of queries that actually retrieve evidence
for it.

The whole claim sentence used to be the query. That is a poor web search
for two reasons, both of which cost real recall:

1. Claims are extracted per sentence, so anaphora is unresolved. "La
   compañía anunció que reducirá sus emisiones un 40%" reaches the search
   engine with no way to know which company - the antecedent was in the
   previous sentence, which the extractor never sees.
2. A long sentence is matched as a bag of words, and its discriminative
   terms (the figure, the year, the organisation) are diluted by the
   prose around them.

So the anchor query is built from the parts that identify the event -
entities, figures, dates - with the article's own subject restored when
the claim does not name one itself.

Then the anchor query alone turned out to have a failure of its own, and
it is worse than thin recall because it produces *confident* answers. A
claim about the Coyote's ACME purchases standing for post-war American
consumerism reached SearXNG as `coyote ACME Estados Unidos Segunda
Guerra Mundial` and came back with three pages explaining that "acme"
means "peak" in Greek. Every anchor matched. The assertion appeared
nowhere. The model cited them as confirmation and the claim was returned
FALSE at 83% confidence.

The fix is not a better single query - it is asking more than one
question and letting the answers vote:

- **anchor**      - who and what, precisely. High precision on the subject.
- **proposition** - what is being *said* about them. The assertion's own
                    content words, which the etymology pages lack.
- **refutation**  - the same event phrased so a contradiction can surface.

Ranked lists from all three are fused by reciprocal rank (see
`fuse_by_rank`), so a page that only one query liked sinks beneath one
that several did.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.models.core.claim import Claim
from src.services.fact_checker.claim_selector import ArticleContext
from src.services.fact_checker.terms import claim_terms, content_terms, subject_terms

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

# How many of the assertion's own words go into the proposition query.
# Enough to describe what is being claimed, few enough that the engine
# still treats them as a conjunction worth satisfying.
MAX_PROPOSITION_WORDS = 6

# How many anchors ride along with the proposition. The assertion's words
# alone would retrieve essays on consumerism; the point is to ask for
# both at once.
MAX_PROPOSITION_ANCHORS = 2

# Reciprocal-rank fusion's damping constant. 60 is the value from the
# original RRF paper and the one every implementation since has used;
# what it buys is that the gap between rank 1 and rank 2 is small
# compared with the gain from appearing in a second list at all - which
# is exactly the property wanted here.
RRF_K = 60


class QueryKind(str, Enum):
    """Which question a query is asking. Carried into the phase events."""

    ANCHOR = "anchor"
    PROPOSITION = "proposition"
    REFUTATION = "refutation"


@dataclass(frozen=True)
class PlannedQuery:

    text: str

    kind: QueryKind


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

    return '"' + term.strip() + '"'


def build_query(
    claim: Claim,
    context: ArticleContext | None = None,
    language: str | None = None,
) -> str:
    """The anchor query: what identifies this claim's event."""

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

    # An entity is not the same as the subject. "convocatorias en Ciudad
    # de México con premios económicos" names a city, so the fallback
    # above never fired - and the query found the city's marathon rather
    # than the aura-farming battles the article was about.
    elif entities:
        parts = subject_terms(claim, context, language) + parts

    # Nothing identifying at all: fall back to the claim's longer words,
    # which is still better than the raw sentence with its stopwords.
    if not parts:
        parts = content_terms(claim.text)[:MAX_FALLBACK_WORDS]

    return " ".join(part.strip() for part in parts if part.strip())


def build_proposition_query(
    claim: Claim,
    context: ArticleContext | None = None,
    language: str | None = None,
) -> str:
    """
    The assertion itself: what the claim says, not only who it is about.

    A couple of anchors are kept alongside the content words. Dropping
    them entirely swings the query to the opposite failure - broad essays
    on the topic with no connection to this event - and the two together
    are what a document has to satisfy to be worth reading.
    """

    # With the context, a subject the sentence lost leads the anchors -
    # so it is what rides along with the assertion's words.
    all_anchors, all_content = claim_terms(claim, language, context)

    content = all_content[:MAX_PROPOSITION_WORDS]

    if not content:
        return ""

    anchors = all_anchors[:MAX_PROPOSITION_ANCHORS]

    # Same anaphora problem as the anchor query, same cheapest available
    # antecedent - but only the title's own content words, since the full
    # headline would swamp six words of assertion.
    if not anchors and context and context.title:
        anchors = content_terms(context.title, language)[:MAX_PROPOSITION_ANCHORS]

    # claim_terms already keeps the two disjoint, so no word is repeated.
    terms = anchors + content

    query = " ".join(terms)

    # A proposition query identical to the anchor query teaches the
    # fusion nothing and spends a search finding the same page twice.
    return "" if query == build_query(claim, context, language) else query


def build_refutation_query(
    claim: Claim,
    context: ArticleContext | None = None,
    language: str | None = None,
) -> str:
    """The same event, asked in a way that can surface a contradiction."""

    base = build_query(claim, context, language)

    if not base:
        return ""

    terms = REFUTATION_TERMS.get(
        (language or "en").lower()[:2],
        REFUTATION_TERMS["en"],
    )

    return f"{base} {terms}"


def plan_queries(
    claim: Claim,
    context: ArticleContext | None = None,
    language: str | None = None,
) -> list[PlannedQuery]:
    """
    Every query this claim should be looked up with, in order.

    Empty queries are dropped rather than sent: an empty search is a
    round-trip that can only return noise, and a blank entry in the live
    view reads as a bug.
    """

    planned = [
        PlannedQuery(build_query(claim, context, language), QueryKind.ANCHOR),
        PlannedQuery(
            build_proposition_query(claim, context, language),
            QueryKind.PROPOSITION,
        ),
        PlannedQuery(
            build_refutation_query(claim, context, language),
            QueryKind.REFUTATION,
        ),
    ]

    seen: set[str] = set()
    unique: list[PlannedQuery] = []

    for query in planned:

        if not query.text or query.text in seen:
            continue

        seen.add(query.text)
        unique.append(query)

    return unique


def fuse_by_rank(ranked_lists: list[list[str]]) -> dict[str, float]:
    """
    Reciprocal rank fusion: `key -> score`, higher is better.

    Concatenating the per-query result lists and deduping by URL - which
    is what this replaces - throws away the single most useful signal the
    multi-query plan produces. A page the anchor query ranked 1st and the
    proposition query never returned at all is a page about the subject
    and not about the claim; a page both returned in their top five is
    the one to read. Only the union of positions can say which is which,
    and RRF is the standard way to say it without having to make the
    engines' incomparable scores comparable.
    """

    scores: dict[str, float] = {}

    for ranked in ranked_lists:
        for rank, key in enumerate(ranked, start=1):
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank)

    return scores
