"""
What a claim is *about*, as terms - shared by the two places that need
the same answer.

Query building and lexical ranking were going to derive this separately,
and they must not: a term the planner considers discriminative enough to
search for is exactly the term a source has to contain to count as
addressing the claim. Two copies of that judgement drift, and the drift
is invisible - retrieval asks for one thing and scoring rewards another.

Terms come in two strengths, because they are not equally identifying:

- **anchors** - named entities, figures and dates. These pin an event.
  A figure or a year is the single most checkable thing a claim carries.
- **content** - the remaining words that survive stopword and
  query-noise filtering. These carry the *assertion*: what is being said
  about the anchors. "consumismo", "representación", "posguerra".

The distinction is the whole point. A claim about the Coyote's ACME
purchases representing post-war consumerism has anchors (Coyote, ACME,
Estados Unidos, Segunda Guerra Mundial) that a search engine will happily
answer with pages explaining the etymology of the word "acme" - every
anchor present, the assertion nowhere in sight. Content terms are what
those pages do not have.
"""

from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING

from src.config.lexicons import lexicon_for
from src.models.core.claim import Claim

if TYPE_CHECKING:
    from src.services.fact_checker.claim_selector import ArticleContext

# Words of 4+ letters. Digits are excluded here on purpose: figures reach
# the query through claim.facts.figures, quoted, rather than as loose
# tokens the engine is free to ignore.
WORD = re.compile(r"\b[^\W\d_]{4,}\b", re.UNICODE)

# Any run of letters or digits, for matching a term inside a document -
# looser than WORD because here we are checking presence, not choosing.
TOKEN = re.compile(r"[^\W_]+", re.UNICODE)

# How much more an anchor counts than a content word when measuring how
# much of a claim a document covers. Not per-run tunable: it is the
# shape of the measure, not a threshold on it.
ANCHOR_WEIGHT = 2.0
CONTENT_WEIGHT = 1.0

# How many of the article's subject words are restored to a claim that
# lost them. Two is a subject ("farmear aura"); more starts describing
# the article rather than naming what it is about.
MAX_SUBJECT_TERMS = 2


def fold(text: str) -> str:
    """
    Lowercased and stripped of accents.

    Spanish evidence is full of both spellings of the same word
    (verificacion / verificación, and every scraped page mangles at least
    one), so comparing terms without folding loses real matches on
    exactly the language where recall is already thinner.
    """

    decomposed = unicodedata.normalize("NFKD", text.lower())

    return "".join(c for c in decomposed if not unicodedata.combining(c))


def anchor_terms(claim: Claim) -> list[str]:
    """The claim's named entities, figures and dates, in that order."""

    entities = [
        value.strip()
        for values in claim.entities.values()
        for value in values
        if value.strip()
    ]

    figures = [figure.strip() for figure in claim.facts.figures if figure.strip()]

    dates = [date.strip() for date in claim.facts.dates if date.strip()]

    return _unique(entities + figures + dates)


def content_terms(text: str, language: str | None = None) -> list[str]:
    """
    The words of `text` that carry its assertion: 4+ letters, minus the
    language's stopwords and query noise, in the order they appear.
    """

    lexicon = lexicon_for(language)

    excluded = {fold(word) for word in lexicon.stopwords | lexicon.query_noise}

    return _unique([
        word
        for word in WORD.findall(text)
        if fold(word) not in excluded
    ])


def subject_terms(
    claim: Claim,
    context: ArticleContext | None = None,
    language: str | None = None,
) -> list[str]:
    """
    The article's subject, when the claim sentence has lost it.

    Claims are extracted one sentence at a time, and a sentence only
    means what it means inside its article. "En agosto de 2026 ya había
    convocatorias en Ciudad de México con premios económicos" comes from
    a piece about *farmear aura* battles in public squares - but the
    sentence never says so, and it carries an entity and a date of its
    own. So it was searched as it stood, retrieved two articles about the
    Mexico City marathon's prize money, and came back TRUE at 84%. Every
    stage matched the sentence. None of them matched the article.

    The subject is the headline's words that the article's own keywords
    agree are central - the intersection is what separates "farmear" and
    "aura" from "volvió" and "viral". Without a headline, the top
    keyword stands in. Empty when the claim already names the subject,
    or when there is no article at all (POST /verify-claim).
    """

    if context is None:
        return []

    title_words = content_terms(context.title, language)

    keyword_tokens = {
        token
        for keyword in context.keywords
        for token in TOKEN.findall(fold(keyword))
    }

    subject = [word for word in title_words if fold(word) in keyword_tokens]

    if not subject and not title_words and context.keywords:
        subject = content_terms(context.keywords[0], language)

    subject = subject[:MAX_SUBJECT_TERMS]

    claim_tokens = set(TOKEN.findall(fold(claim.text)))

    if any(fold(word) in claim_tokens for word in subject):
        return []

    return subject


def contextualised_claim(
    claim: Claim,
    context: ArticleContext | None = None,
    language: str | None = None,
) -> str:
    """
    The claim's text with a lost subject put back in front - what gets
    embedded to judge a source against. Shared by the retriever and the
    ranker so the funnel and the pertinence gate judge the same claim.
    """

    return " ".join(subject_terms(claim, context, language) + [claim.text])


def claim_terms(
    claim: Claim,
    language: str | None = None,
    context: ArticleContext | None = None,
) -> tuple[list[str], list[str]]:
    """
    `(anchors, content)` for one claim, with the two sets kept disjoint.

    The disjointness is the point and it was worth a bug to learn. An
    entity's own words also survive content-word filtering, so "ACME" and
    "Estados Unidos" were counted once as anchors and again as content -
    and since anchors are weighted double, a page that named every entity
    and addressed nothing scored half marks. That is exactly the
    etymology page the gate exists to cut, passing the gate.

    With a `context`, the article's subject is restored as the leading
    anchors when the sentence lost it (`subject_terms`). Leading, because
    the proposition query keeps only the first couple of anchors, and a
    source that never mentions the subject is about something else.
    """

    anchors = _unique(subject_terms(claim, context, language) + anchor_terms(claim))

    inside_an_anchor = {
        token
        for anchor in anchors
        for token in TOKEN.findall(fold(anchor))
    }

    content = [
        word
        for word in content_terms(claim.text, language)
        if fold(word) not in inside_an_anchor
    ]

    return anchors, content


def coverage(text: str, anchors: list[str], content: list[str]) -> float:
    """
    How much of a claim this text actually contains, 0-1.

    Weighted rather than a plain ratio, so a page carrying every name and
    none of the assertion does not score the same as one carrying both.
    An empty claim (no terms at all) scores 0.0 rather than 1.0: nothing
    was checked, so nothing is covered - returning a perfect score for
    "we had nothing to look for" is how a gate stops gating.
    """

    if not anchors and not content:
        return 0.0

    haystack = set(TOKEN.findall(fold(text)))

    folded_haystack = fold(text)

    total = 0.0
    found = 0.0

    for term in anchors:
        total += ANCHOR_WEIGHT
        # Multi-word entities ("Segunda Guerra Mundial") are matched as a
        # phrase, single words against the token set so a substring like
        # "acme" inside "acmefoundation" does not count.
        if _present(term, haystack, folded_haystack):
            found += ANCHOR_WEIGHT

    for term in content:
        total += CONTENT_WEIGHT
        if _present(term, haystack, folded_haystack):
            found += CONTENT_WEIGHT

    return found / total if total else 0.0


def _present(term: str, tokens: set[str], text: str) -> bool:

    folded = fold(term)

    if " " in folded:
        return folded in text

    return folded in tokens


def _unique(values: list[str]) -> list[str]:
    """Order-preserving dedupe, case- and accent-insensitive."""

    seen: set[str] = set()
    unique: list[str] = []

    for value in values:

        key = fold(value)

        if key in seen:
            continue

        seen.add(key)
        unique.append(value)

    return unique
