"""
What the verifier reads of each source.

The model reads its prompt at CPU speed - about fifty tokens a second for
`llama3.2:3b` on the dev machine's CPU, measured 2026-10-21 - and on a
claim that is two thirds of the call: 29 s reading 1,421 tokens, 16 s
writing 103. Five sources at 1,500 characters each are most of those
tokens, and the 1,500 were always the page's *first* 1,500: its headline
block, its standfirst, often a cookie notice - rarely the paragraph that
says what the claim says.

`passages` keeps the sentences that carry the claim's terms instead,
judged by the same `terms.py` arithmetic that built the queries and that
the pertinence gate cut on, so retrieval, ranking and reading agree on
what a claim is about. Fewer characters, chosen for the claim rather
than by position. Whether that reads as well is measured, not assumed:
docs/decisions/performance.md.
"""

from __future__ import annotations

import re

from src.services.fact_checker.terms import coverage

# A sentence: a run up to its closing punctuation (and any closing quote
# or bracket after it), or up to a line break - scraped pages put
# headings, captions and list items on lines of their own, unpunctuated.
SENTENCE = re.compile(r"[^.!?…\n]+(?:[.!?…]+[\"'»”’)\]]*)?")

# Between two passages that are not next to each other on the page, so
# the model is not shown two distant sentences as if one followed the
# other.
GAP = " … "


def head(text: str, budget: int) -> str:
    """The first `budget` characters: what every run read until 2026-10-21."""

    return text[:budget]


def passages(text: str, budget: int, anchors: list[str], content: list[str]) -> str:
    """
    The sentences of `text` that cover most of the claim, in page order,
    within `budget` characters.

    Best-covering first; a sentence that does not fit is skipped for a
    shorter one rather than cut, so every sentence shown is whole and a
    quote the model copies from it is findable in the page. What budget
    is left goes to the page's opening sentences, which say what the page
    is about. A page that never mentions a term of the claim gets its
    head, as before: nothing to choose by.
    """

    if len(text) <= budget:
        return text

    spans = [
        (match.start(), match.end())
        for match in SENTENCE.finditer(text)
        if match.group().strip()
    ]

    scores = [coverage(text[start:end], anchors, content) for start, end in spans]

    if not any(score > 0 for score in scores):
        return head(text, budget)

    chosen: set[int] = set()
    used = 0

    by_coverage = sorted(
        (index for index, score in enumerate(scores) if score > 0),
        key=lambda index: (-scores[index], index),
    )

    # Then the opening, in order, with whatever room is left.
    for index in by_coverage + list(range(len(spans))):

        if index in chosen:
            continue

        start, end = spans[index]
        cost = len(text[start:end].strip()) + len(GAP)

        if used + cost > budget:
            continue

        chosen.add(index)
        used += cost

    if not chosen:
        return head(text, budget)

    return _render(text, spans, sorted(chosen))


def _render(text: str, spans: list[tuple[int, int]], indices: list[int]) -> str:
    """Neighbouring sentences joined by a space, separated ones by GAP."""

    parts: list[str] = []
    previous = None

    for index in indices:

        start, end = spans[index]
        sentence = text[start:end].strip()

        if previous is not None:
            parts.append(" " if index == previous + 1 else GAP)

        parts.append(sentence)
        previous = index

    return "".join(parts)
