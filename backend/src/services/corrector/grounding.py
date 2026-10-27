"""
The checks of a draft's grounding that need no model.

The review's model judges whether each cited source says what the
sentence says; that takes reading. Three things do not, and are checked
here so they are reported whatever the model makes of the draft - a small
local model reads a long prompt unevenly, and these are exactly what it
misses:

- **a factual sentence with no citation.** "Factual" is a heuristic: a
  figure, a month, a unit, or a reporting verb ("announced", "va
  anunciar") from the draft language's lexicon. Opinion and transition
  sentences have none and are not asked to cite anything.
- **a citation that points nowhere**: `[n]` with no n-th source.
- **a sentence that repeats a claim the pipeline judged FALSE,
  MISLEADING or UNVERIFIED.** By word overlap with the claim, so it
  works only when the draft is written in the analysed article's
  language, and it cannot tell a sentence asserting the claim from one
  refuting it. Reported for a person to look at, never scored.

The body is the small Markdown `ArticleBody` renders (frontend
components/drafts/ArticleBody.tsx): blocks split on blank lines, `#`
headings, `- ` lists. Citations are `[n]`, 1-based into
`ArticleDraft.sources`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from src.config.lexicons import WRITING_LEXICONS, Lexicon, matches
from src.models.writer.draft import DraftFactCheck
from src.services.corrector.draft_language import WORD, prepare_for_scoring

CITATION = re.compile(r"\[(\d+)\]")

# A sentence ends at . ! ? or … followed by space and the start of the
# next one. Citations right after the stop ("in 2015. [1] Fish ...")
# belong to the sentence they follow, so they are captured with it.
_BOUNDARY = re.compile(
    r"(?<=[.!?…])((?:\s*\[\d+\])*)\s+(?=[\"'«“¿¡(]?[A-ZÀ-ÖØ-Þ0-9])"
)

# Verdicts a draft must not state as fact. PARTIALLY_TRUE is left out:
# its central assertion held.
FLAGGED_VERDICTS = ("FALSE", "MISLEADING", "UNVERIFIED")

# How much of a flagged claim's content a sentence must share to be
# reported as repeating it, and how many content words the claim needs
# for that share to mean anything.
ECHO_OVERLAP = 0.6
ECHO_MIN_TERMS = 3

# How long a quoted sentence may run in an issue before it is cut.
QUOTE_CHARS = 160

# Sentences shorter than this are fragments (a dateline, "Why it
# matters."), not statements to source.
MIN_FACTUAL_WORDS = 5


@dataclass
class Echo:

    sentence: str

    claim: str

    verdict: str


@dataclass
class Grounding:

    # Sentences that state something checkable and cite nothing.
    uncited: list[str] = field(default_factory=list)

    # (sentence, n) for every [n] with no n-th source.
    dangling: list[tuple[str, int]] = field(default_factory=list)

    echoes: list[Echo] = field(default_factory=list)

    # How many sentences looked factual at all - what `uncited` is a
    # share of.
    factual: int = 0


# ----------------------------------------------------------------------
# Reading the body
# ----------------------------------------------------------------------


def body_sentences(body: str) -> list[str]:
    """Every sentence of the body, list items included, headings left out."""

    sentences: list[str] = []

    for block in re.split(r"\n\s*\n", body.replace("\r\n", "\n")):

        block = block.strip()

        if not block or block.startswith("#"):
            continue

        lines = [line.strip() for line in block.split("\n") if line.strip()]

        if all(re.match(r"^[-*] ", line) for line in lines):
            units = [line[2:].strip() for line in lines]
        else:
            units = [" ".join(lines)]

        for unit in units:
            split = _BOUNDARY.sub(lambda match: f"{match.group(1)}\n", unit)
            sentences.extend(part.strip() for part in split.split("\n") if part.strip())

    return sentences


def citations(text: str) -> list[int]:

    return [int(number) for number in CITATION.findall(text)]


def plain(text: str) -> str:
    """Markdown and citation markers out: what a reader's eye reads."""

    text = CITATION.sub("", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[-*]\s+", "", text, flags=re.MULTILINE)
    text = text.replace("**", "")

    return re.sub(r"[ \t]+([.,;:!?])", r"\1", text)


def quote(sentence: str) -> str:

    sentence = " ".join(sentence.split())

    if len(sentence) <= QUOTE_CHARS:
        return f"“{sentence}”"

    return f"“{sentence[:QUOTE_CHARS].rstrip()}…”"


# ----------------------------------------------------------------------
# The checks
# ----------------------------------------------------------------------


def _words(text: str, language: str) -> list[str]:

    return [word.lower() for word in WORD.findall(prepare_for_scoring(CITATION.sub(" ", text), language))]


def is_factual(sentence: str, lexicon: Lexicon) -> bool:
    """
    Whether a sentence states something a reader could check: a figure,
    a month, or someone named reporting something ("the University of
    Girona found", "Barcelona va anunciar").

    A reporting verb alone is not enough: the lexicons' verb lists are
    prefixes built for recall ("public*" is also "público", "informa*"
    also "informació"), and a sentence counted as factual here that cites
    nothing lowers its score. The named subject is what makes it a
    report. Units are left out for the same reason: "people" and
    "persones" are units in those lists.
    """

    words = _words(sentence, lexicon.language)

    if len(words) < MIN_FACTUAL_WORDS:
        return False

    if re.search(r"\d", CITATION.sub(" ", sentence)):
        return True

    if any(matches(word, lexicon.month_names) for word in words):
        return True

    reports = any(matches(word, lexicon.reporting_verbs) for word in words if len(word) > 1)

    return reports and _names_someone(sentence, lexicon.language)


def _names_someone(sentence: str, language: str) -> bool:
    """A capitalised word after the first: a name, a place, an institution."""

    tokens = WORD.findall(prepare_for_scoring(CITATION.sub(" ", sentence), language))

    return any(token[:1].isupper() and len(token) > 1 for token in tokens[1:])


def _fold(word: str) -> str:

    return "".join(
        character
        for character in unicodedata.normalize("NFKD", word)
        if not unicodedata.combining(character)
    )


# Words that carry no claim in any writing language. A fact-check's
# claim is in the analysed article's language, which need not be the
# draft's.
_NOISE = frozenset(
    _fold(word)
    for lexicon in WRITING_LEXICONS.values()
    for word in lexicon.stopwords | lexicon.query_noise
)


def _terms(text: str, language: str) -> set[str]:
    """
    Content stems: accents folded, short and function words out, cut to
    six characters so "doubled" meets "doubling" and "duplicat" meets
    "duplicada". Figures are kept whole - they are most of what a claim
    asserts.
    """

    terms = set()

    for word in _words(text, language):

        word = _fold(word)

        if word.isdigit():
            terms.add(word)
        elif len(word) >= 4 and word not in _NOISE:
            terms.add(word[:6])

    return terms


def figures(text: str) -> set[str]:
    """Every run of digits outside the citation markers."""

    return set(re.findall(r"\d+", CITATION.sub(" ", text)))


# A sentence of a proposal that cites [n] must share at least this much of
# its content with some sentence of the draft that cited [n]. Low, so a
# copy-edit's rephrasing passes ("has doubled since 2015" -> "since 2015,
# has doubled in size"); a citation moved onto another statement shares
# nothing with where it was.
MIN_ATTACHED_SHARE = 0.25

# When the source's own text is given (a rewrite, which reads it), a
# citation the draft did not have on that statement stands if at least
# this much of the sentence's content is in the source's excerpt. Higher
# than MIN_ATTACHED_SHARE because an excerpt is long - [1] is up to 6,000
# characters - and a quarter of any sentence about the story is in it.
# Reasoned, not fitted. Same-language only, like every term comparison
# here: a Catalan sentence shares almost no stems with an English source,
# so a rewrite of a Catalan draft can keep its citations but not add one.
MIN_SOURCE_SHARE = 0.5


def repointed(
    original: str,
    proposed: str,
    language: str,
    sources: dict[int, str] | None = None,
) -> list[tuple[str, int]]:
    """
    (sentence, n) for every sentence of `proposed` that cites [n] but
    says nothing the draft's [n]-citing sentences said: the citation now
    vouches for a statement its source was never cited for. Measured live
    on 2026-10-15: llama3.2:3b moved a [1] onto "the bay is no longer free
    of plastics", which source 1 never mentions.

    `sources` maps n to the text of source n the writer saw. When given,
    a sentence that shares MIN_SOURCE_SHARE of its content with that text
    is not reported: it says what its source says, wherever the draft
    cited it before. The review's proposal never sees the sources and
    passes none.
    """

    before: dict[int, list[set[str]]] = {}

    for sentence in body_sentences(original):
        terms = _terms(sentence, language)
        for number in set(citations(sentence)):
            before.setdefault(number, []).append(terms)

    in_source = {number: _terms(text, language) for number, text in (sources or {}).items()}

    moved = []

    for sentence in body_sentences(proposed):

        terms = _terms(sentence, language)

        if len(terms) < 2:
            continue

        for number in sorted(set(citations(sentence))):

            best = max((len(terms & earlier) / len(terms) for earlier in before.get(number, [])), default=0.0)

            if best >= MIN_ATTACHED_SHARE:
                continue

            if number in in_source and len(terms & in_source[number]) / len(terms) >= MIN_SOURCE_SHARE:
                continue

            moved.append((sentence, number))

    return moved


def stating(body: str, claim: str, lexicon: Lexicon) -> list[str]:
    """
    The body's sentences that state `claim`, by the echo rule: sharing
    ECHO_OVERLAP of its content terms, when it has ECHO_MIN_TERMS of them.
    What the review holds a draft from a trend's confirmed angle to.
    """

    claim_terms = _terms(claim, lexicon.language)

    if len(claim_terms) < ECHO_MIN_TERMS:
        return []

    return [
        sentence
        for sentence in body_sentences(body)
        if len(claim_terms & _terms(sentence, lexicon.language)) / len(claim_terms) >= ECHO_OVERLAP
    ]


def check(
    body: str,
    source_count: int,
    fact_checks: list[DraftFactCheck],
    lexicon: Lexicon,
) -> Grounding:

    grounding = Grounding()

    flagged = [
        (fact_check, _terms(fact_check.claim, lexicon.language))
        for fact_check in fact_checks
        if fact_check.verdict.upper() in FLAGGED_VERDICTS
    ]

    for sentence in body_sentences(body):

        cited = citations(sentence)

        for number in cited:
            if not 1 <= number <= source_count:
                grounding.dangling.append((sentence, number))

        if is_factual(sentence, lexicon):

            grounding.factual += 1

            if not cited:
                grounding.uncited.append(sentence)

        terms = _terms(sentence, lexicon.language)

        for fact_check, claim_terms in flagged:

            if len(claim_terms) < ECHO_MIN_TERMS:
                continue

            if len(claim_terms & terms) / len(claim_terms) >= ECHO_OVERLAP:
                grounding.echoes.append(
                    Echo(sentence=sentence, claim=fact_check.claim, verdict=fact_check.verdict.upper())
                )

    return grounding
