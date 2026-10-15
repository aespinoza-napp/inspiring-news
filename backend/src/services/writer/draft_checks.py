"""
What is checked in the writer's answer without a model
(docs/decisions/writing.md, "Writing").

Two kinds:

- **repairs**, applied to the text: the Markdown reduced to what
  components/drafts/ArticleBody.tsx renders (paragraphs, `##`/`###`,
  `- ` lists, `**bold**`), and every citation made to point at a source
  that exists - `[2, 3]` and `[2-3]` become `[2][3]`, and a number past
  the end of the list is dropped. A citation that points nowhere is
  worse than none: the page links it to a source that is not there.
- **findings**, reported and left alone: sentences with no citation,
  passages copied from the analysed article, numbers no source contains.
  They need a judgement this module cannot make - a number can be a
  correct conversion, a run of words can be a name - and that judgement
  is the review stage's. The draft has no field for them yet, so the
  writer logs them.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# A citation group: [3], [2, 3], [2-4], [2; 4].
CITATION = re.compile(r"\[(\s*\d+(?:\s*[-–,;]\s*\d+)*\s*)\]")

# A range wider than this is not a citation (a year span, "[1990-2020]").
MAX_RANGE = 10

# A copied passage is this many words in a row shared with the article.
OVERLAP_WORDS = 12

_WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)

# Digits, with the thousands separators English, Spanish and Catalan
# write them with (a comma, a point, a no-break or narrow no-break space)
# - never a plain space, which would read "in 2026 300 people" as one.
_NUMBER = re.compile(r"\d+(?:[.,  ]\d{3})*(?:[.,]\d+)?")


@dataclass
class Checked:

    body: str

    # Citation numbers that pointed past the sources and were removed.
    dropped_citations: list[int] = field(default_factory=list)

    findings: list[str] = field(default_factory=list)


# ----------------------------------------------------------------------
# Markdown
# ----------------------------------------------------------------------


def _inline(line: str) -> str:

    # Images go; a link keeps its text - unless the text is a citation
    # number, which keeps its brackets. No link the model made reaches the
    # page: a URL it wrote is one more thing it could have invented.
    line = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", line)
    line = re.sub(r"\[(\d+)\]\([^)]*\)", r"[\1]", line)
    line = re.sub(r"\[([^\]]+)\]\((?:https?://|/|#)[^)]*\)", r"\1", line)

    # Raw HTML is shown as text by the renderer, so it is removed here.
    line = re.sub(r"</?[a-zA-Z][^>]*>", "", line)

    # __bold__ is bold; *italic* has no rendering and would show its stars.
    line = re.sub(r"__(?=\S)(.+?)(?<=\S)__", r"**\1**", line)
    line = re.sub(r"(?<![*\w])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![*\w])", r"\1", line)

    # What a removed tag or image leaves behind.
    return re.sub(r"[ \t]{2,}", " ", line).rstrip()


def normalise_markdown(body: str, title: str = "") -> str:
    """
    The body as blocks the renderer understands, separated by one blank
    line: a heading alone, a run of `- ` items, or a paragraph. A heading
    or a list sharing a block with prose would render as one heading, or
    one paragraph with dashes in it.
    """

    lines = (body or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")

    blocks: list[list[str]] = []
    kind: str | None = None
    fenced = False

    def close() -> None:
        nonlocal kind
        kind = None

    for raw in lines:

        line = raw.strip()

        # A code block carries nothing an article needs, fence and all.
        if line.startswith("```"):
            fenced = not fenced
            close()
            continue

        if fenced:
            continue

        if not line:
            close()
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", line)

        if heading:
            text = _inline(heading.group(2)).strip(" #")
            if text:
                level = "###" if len(heading.group(1)) >= 3 else "##"
                blocks.append([f"{level} {text}"])
            close()
            continue

        item = re.match(r"^(?:[-*•+]|\d+[.)])\s+(.*)$", line)

        if item:
            text = _inline(item.group(1)).strip()
            if not text:
                continue
            if kind != "list":
                blocks.append([])
                kind = "list"
            blocks[-1].append(f"- {text}")
            continue

        text = _inline(line).strip()

        if not text:
            continue

        if kind != "paragraph":
            blocks.append([])
            kind = "paragraph"

        blocks[-1].append(text)

    # The title repeated as the body's first heading.
    if blocks and title and re.sub(r"^#+\s*", "", blocks[0][0]).strip().casefold() == title.strip().casefold():
        blocks = blocks[1:]

    return "\n\n".join(
        block[0] if block[0].startswith("#") else "\n".join(block)
        for block in blocks
    )


# ----------------------------------------------------------------------
# Citations
# ----------------------------------------------------------------------


def _numbers(group: str) -> list[int] | None:

    numbers: list[int] = []

    for part in re.split(r"\s*[,;]\s*", group.strip()):

        span = re.split(r"\s*[-–]\s*", part)

        if len(span) == 1:
            numbers.append(int(span[0]))
            continue

        start, end = int(span[0]), int(span[1])

        if end < start or end - start > MAX_RANGE:
            return None

        numbers.extend(range(start, end + 1))

    return numbers


def repair_citations(body: str, count: int) -> tuple[str, list[int]]:
    """
    Every citation as `[n]` with 1 <= n <= count. Out-of-range numbers are
    dropped; a group that is not a citation at all (a year span) is left
    as written.
    """

    dropped: list[int] = []

    def fix(match: re.Match) -> str:

        numbers = _numbers(match.group(1))

        if numbers is None:
            return match.group(0)

        kept = []

        for number in numbers:
            if 1 <= number <= count:
                if number not in kept:
                    kept.append(number)
            else:
                dropped.append(number)

        return "".join(f"[{number}]" for number in kept)

    repaired = CITATION.sub(fix, body)

    # A removed citation leaves its space behind: "rose [9]." -> "rose ."
    repaired = re.sub(r"[ \t]+([.,;:!?)])", r"\1", repaired)
    repaired = re.sub(r"[ \t]{2,}", " ", repaired)

    return repaired, dropped


def cited_numbers(body: str) -> set[int]:

    return {
        number
        for match in CITATION.finditer(body)
        for number in (_numbers(match.group(1)) or [])
    }


# ----------------------------------------------------------------------
# Findings
# ----------------------------------------------------------------------


def _plain(text: str) -> str:

    return CITATION.sub(" ", text).replace("**", "")


def uncited_sentences(body: str) -> list[str]:
    """Sentences of prose (not headings) carrying no citation."""

    sentences = []

    for block in body.split("\n\n"):

        if block.startswith("#"):
            continue

        for line in block.split("\n"):

            text = line[2:] if line.startswith("- ") else line

            # Split where a sentence ends and a capitalised one begins. A
            # citation placed after the full stop stays with the text
            # around it, so the check errs towards "cited".
            for sentence in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý¿¡\"“«])", text):

                if len(_WORD.findall(_plain(sentence))) >= 6 and not CITATION.search(sentence):
                    sentences.append(sentence.strip())

    return sentences


def _words(text: str) -> list[str]:

    return [word.casefold() for word in _WORD.findall(_plain(text))]


def verbatim_overlaps(body: str, original: str, size: int = OVERLAP_WORDS) -> list[str]:
    """
    Runs of at least `size` words the body shares, word for word, with
    `original` - the analysed article, which the draft must paraphrase.
    """

    if not original:
        return []

    source = _words(original)

    grams = {tuple(source[i:i + size]) for i in range(len(source) - size + 1)}

    words = _words(body)

    runs: list[str] = []

    index = 0

    while index <= len(words) - size:

        if tuple(words[index:index + size]) not in grams:
            index += 1
            continue

        end = index + size

        while end < len(words) and tuple(words[end - size + 1:end + 1]) in grams:
            end += 1

        runs.append(" ".join(words[index:end]))

        index = end

    return runs


def _normalised_number(token: str) -> str:

    return re.sub(r"[.,  ]", "", token)


def unsupported_numbers(body: str, texts: list[str]) -> list[str]:
    """
    Numbers in the body that appear in none of `texts` (the excerpts the
    writer was given and the claims it was told about), separators
    ignored, so 40,000 and 40.000 are one number. A number written in
    words in a source shows up here too - a finding, not a verdict.
    """

    known = {
        _normalised_number(token)
        for text in texts
        for token in _NUMBER.findall(text or "")
    }

    unsupported = []

    for token in _NUMBER.findall(_plain(body)):

        normalised = _normalised_number(token)

        if normalised not in known and token not in unsupported:
            unsupported.append(token.strip())

    return unsupported


def check(
    body: str,
    title: str,
    source_count: int,
    original: str | None,
    texts: list[str],
) -> Checked:
    """The repairs, then the findings on the repaired text."""

    body = normalise_markdown(body, title)

    body, dropped = repair_citations(body, source_count)

    findings = []

    if dropped:
        findings.append(f"removed {len(dropped)} citation(s) past the {source_count} sources: {sorted(set(dropped))}")

    uncited = uncited_sentences(body)

    if uncited:
        findings.append(f"{len(uncited)} sentence(s) with no citation, e.g. {uncited[0][:120]!r}")

    copied = verbatim_overlaps(body, original or "")

    if copied:
        findings.append(f"{len(copied)} passage(s) copied word for word from the analysed article, e.g. {copied[0][:160]!r}")

    numbers = unsupported_numbers(body, texts)

    if numbers:
        findings.append(f"numbers found in no source excerpt: {', '.join(numbers[:12])}")

    return Checked(body=body, dropped_citations=dropped, findings=findings)


def slugify(text: str, limit: int = 80) -> str:
    """ASCII, lowercase, hyphens: "Les praderies tornen" -> "les-praderies-tornen"."""

    ascii_text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")

    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")

    return slug[:limit].rstrip("-")
