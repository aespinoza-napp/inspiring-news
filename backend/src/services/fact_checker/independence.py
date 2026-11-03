"""
Whether a source says anything of its own about a claim, read without a
model: does it carry the claim's sentence word for word, or the same
sentence with one detail changed?

**A copy is not corroboration.** The Guardian's piece on Jamaica's beaches
was marked TRUE on `thenote.app`, `newsminimalist.com` and
`lipstickalley.com`, each quoting the article's own sentence: aggregators
repeating the article back to itself. Dropping the article's own URL
(`EvidenceRetriever._without_the_article`) never caught them. Measured on
the train half (run cc053417c0cb, 2026-10-29): 12 of 69 claims had such a
page, 17 of 303 judged sources, 15 of them "supports" - and the sentence
also misleads the other way, the 3B marking pages as *contradicting* a
claim while quoting that very sentence from them (HPV article, 2026-11-03).
A page that repeats the sentence cannot say if it is true, so it is taken
out of the evidence, with the reason kept among the rejected sources. It
may be the article's own source, a wire or a press release: that still is
one voice, not two.

**The same sentence with one detail changed is a contradiction a model
misses.** "...for some 168 km" against a page reading "...for some 68 km":
the 3B answered "supports", on the point the per-source verifier is
weakest at (altered claims 60 -> 13%, docs/fact-checking-changes.md, 6). No
reading is needed to see that two sentences differ in one figure, so none
is asked for: the source is recorded as contradicting, with that sentence
as its quote, and the claim is FALSE. On the train half it fired on 4
sources of 3 altered claims and on none of the 54 natural ones. When a page
also carries the claim word for word the outlets disagree with each other,
which settles nothing, so the sources go to the model as usual
(`decisive_altered`).

Bear in mind what that measurement can and cannot say: the set's altered
claims were made by changing a detail of a real sentence, the very thing
this looks for, so its gain on them overstates what it would find in the
wild. The figure to trust is the false alarms on natural claims.

Word-level, on purpose: tokens rather than characters, so punctuation and
accents do not count as differences, and only a short replacement counts
as a changed detail. A rewording is neither a copy nor a contradiction, and
is left to the model.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from src.models.core.claim import Claim
from src.models.fact_checker.evidence import Evidence, RejectedEvidence
from src.models.fact_checker.pipeline_stage import PipelineStage
from src.services.fact_checker.terms import fold

# Under this the sentence is too short to call a repeat of it a copy:
# "El Gobierno lo aprobó ayer" can be written twice independently.
MIN_CLAIM_WORDS = 8

# How much of the claim a sentence of the source has to hold, in order.
COPY_SHARE = 0.97
ALTERED_SHARE = 0.75

# Sentences sharing less than this of the claim's words are not compared:
# the alignment is the slow part and most of a page is about something else.
CANDIDATE_OVERLAP = 0.6

# A changed detail is a short replacement, on both sides. Anything longer is
# a rewording, however close the rest is ("charting a path towards a world
# where" / "aiming to ensure").
MAX_CHANGED_WORDS = 3
MAX_CHANGES = 2

# Letters two words share, above which they are taken for one word inflected.
SAME_WORD_SIMILARITY = 0.6

# Words whose replacement changes no fact, in the two languages the
# pipeline reads.
_FUNCTION_WORDS = frozenset(
    "the a an of in on at to and or for with by from that this is was were are has have had it its "
    "de la el los las en y o un una que del al se su por con para es fue".split()
)

_TOKEN = re.compile(r"[^\W_]+(?:[.,]\d+)*", re.UNICODE)
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+|\n+")
_DIGIT = re.compile(r"\d")


@dataclass(frozen=True)
class Comparison:

    # "copy", "altered", or "independent".
    relation: str = "independent"

    # The source's sentence, for a copy or an altered detail.
    sentence: str | None = None

    # (what the claim says, what the source says), for an altered detail.
    changes: list[tuple[str, str]] = field(default_factory=list)


def _tokens(text: str | None) -> list[str]:
    return _TOKEN.findall(fold(text or ""))


def _sentences(text: str | None) -> list[str]:
    return [sentence for sentence in _SENTENCE_END.split(text or "") if sentence.strip()]


def _is_detail(said: list[str], instead: list[str]) -> bool:
    """Whether replacing `said` with `instead` changes a fact rather than a word."""

    said = [word for word in said if word not in _FUNCTION_WORDS]
    instead = [word for word in instead if word not in _FUNCTION_WORDS]

    if not said or not instead:
        return False

    if any(_DIGIT.search(word) for word in said + instead):
        return set(said) != set(instead)

    # Words: "spring" / "summer", not "report" / "reports" or "found" /
    # "finds", which are one word inflected, in either language.
    return (
        all(len(word) >= 4 for word in said + instead)
        and difflib.SequenceMatcher(None, said[0], instead[0]).ratio() < SAME_WORD_SIMILARITY
    )


def compare(sentence: str, text: str | None) -> Comparison:
    """The source's sentence nearest `sentence`, and what it amounts to."""

    claim = _tokens(sentence)

    if len(claim) < MIN_CLAIM_WORDS or not text:
        return Comparison()

    words = set(claim)
    best: tuple[float, list, list[str], str] | None = None

    for candidate in _sentences(text):

        tokens = _tokens(candidate)

        if len(words & set(tokens)) < CANDIDATE_OVERLAP * len(words):
            continue

        matcher = difflib.SequenceMatcher(None, claim, tokens, autojunk=False)

        share = sum(block.size for block in matcher.get_matching_blocks()) / len(claim)

        if best is None or share > best[0]:
            best = (share, matcher.get_opcodes(), tokens, candidate.strip())

    if best is None:
        return Comparison()

    share, operations, tokens, candidate = best

    if share >= COPY_SHARE:
        return Comparison(relation="copy", sentence=candidate)

    if share < ALTERED_SHARE:
        return Comparison()

    replaced = [
        (claim[start:end], tokens[other_start:other_end])
        for operation, start, end, other_start, other_end in operations
        if operation == "replace"
    ]

    if not replaced or len(replaced) > MAX_CHANGES:
        return Comparison()

    if any(len(said) > MAX_CHANGED_WORDS or len(instead) > MAX_CHANGED_WORDS for said, instead in replaced):
        return Comparison()

    changes = [(" ".join(said), " ".join(instead)) for said, instead in replaced if _is_detail(said, instead)]

    if not changes:
        return Comparison()

    return Comparison(relation="altered", sentence=candidate, changes=changes)


def sentence_of(claim: Claim) -> str:
    """What the article wrote: a restated claim is compared by its original sentence."""

    return claim.written_as or claim.text


def page_text(item: Evidence) -> str:
    """Everything the source shows: its title can be the sentence itself."""

    return "\n".join(part for part in (item.title, item.snippet, item.content) if part)


@dataclass
class Sorted:

    # Everything that can still be weighed, altered sources included.
    kept: list[Evidence] = field(default_factory=list)

    copies: list[RejectedEvidence] = field(default_factory=list)

    # Each source carrying the sentence with a detail changed, by URL.
    altered: dict[str, Comparison] = field(default_factory=dict)


def sort_sources(claim: Claim, candidates: list[Evidence]) -> Sorted:
    """The copies out, the altered marked; input order kept, since evidence order is what gets cited."""

    sentence = sentence_of(claim)
    result = Sorted()

    for item in candidates:

        comparison = compare(sentence, page_text(item))

        if comparison.relation == "copy":
            result.copies.append(RejectedEvidence(
                url=item.url,
                title=item.title,
                origin=item.origin,
                stage=PipelineStage.EVIDENCE_RETRIEVAL,
                reason="repeats the claim's sentence word for word: a copy says nothing independent",
                score=item.relevance_score,
            ))
            continue

        if comparison.relation == "altered":
            result.altered[item.url] = comparison

        result.kept.append(item)

    return result


def decisive_altered(found: Sorted, ranked: list[Evidence]) -> list[int]:
    """
    Which ranked sources settle the claim as FALSE by themselves: those
    with a changed detail, unless a page also repeats the claim word for
    word - then outlets disagree about the detail, and that is not settled
    by counting the sentence's copies.
    """

    if found.copies:
        return []

    return [index for index, item in enumerate(ranked) if item.url in found.altered]


def describe(found: Sorted, ranked: list[Evidence], indices: list[int]) -> str:
    """The reason in the verdict's own words: which source, and what it says instead."""

    parts = []

    for index in indices:

        item = ranked[index]
        changes = "; ".join(
            f'"{instead}" where the claim says "{said}"'
            for said, instead in found.altered[item.url].changes
        )

        parts.append(f"[{index}] {item.domain or item.url} carries the same sentence with {changes}")

    return "; ".join(parts) + "."
