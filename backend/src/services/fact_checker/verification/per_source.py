"""
The verifier asked about one source at a time (VERIFIER_ANSWER=per_source).

The list verifier asks the model to read every source and weigh them in
one answer. On 2026-10-22 the 3B did that by answering FALSE to 21 of the
45 true train claims, each time marking one source "contradicts", and
most of them explained as "the evidence does not mention ..."
(data/evaluation/experiments/verifier/rule.md). Here each source is one
short question - does it state the claim, state something that cannot be
true with it, say nothing on it, or is it about something else - and the
verdict follows from the answers by a rule a reader can check:

- some source states it and none states otherwise: TRUE;
- sources state otherwise: FALSE when more outlets state otherwise than
  state it, else TRUE, which the scorer then makes PARTIALLY_TRUE for the
  contradicting source (ConfidenceScorer);
- no source states it either way: UNVERIFIED.

A contradiction counts with or without its quote: the quote is checked
(LLMVerifier._validate_quote) and kept only when it is really in the
source, but a 3B often fails to copy a sentence exactly even when it read
it right.

The calls are made one after the other on the claim's own thread: the
model takes one call at a time on every CPU setup (LLM_MAX_CONCURRENCY),
and the evaluation harness attributes a call to its claim by thread.
"""

from dataclasses import dataclass

from src.models.fact_checker.evidence import Evidence, EvidenceStance
from src.models.fact_checker.fact_check import Verdict

PER_SOURCE_SYSTEM_PROMPT = (
    "You check one claim from a news article against one source. The "
    "article's headline and opening may be given for context.\n\n"
    "Respond with ONLY a JSON object:\n"
    '{"stance": "supports" | "contradicts" | "silent" | "unrelated", '
    '"quote": "<the sentence of the source that supports or contradicts the claim, '
    'copied word for word; empty otherwise>"}\n\n'
    "- supports: the source states what the claim says - its point, and its "
    "figures, dates and names.\n"
    "- contradicts: the source states something that cannot be true at the "
    "same time as the claim - another figure, date, person or outcome for "
    "the same thing.\n"
    "- silent: the source is about the claim's subject but does not say "
    "whether the claim is true. A detail the source does not mention is "
    "silent, never contradicts.\n"
    "- unrelated: the source is about a different event or subject, even if "
    "it shares a place, a date or a figure with the claim.\n"
    "- Judge the claim about its article's subject when the article is given."
)

# A stance and one sentence: ~15-60 tokens. This only stops a loop.
PER_SOURCE_MAX_ANSWER_TOKENS = 160

_STANCES = {stance.value: stance for stance in EvidenceStance}


@dataclass(frozen=True)
class SourceAnswer:

    index: int

    # None: not judged - no usable answer, the model unreachable, or the
    # claim out of time before this source's turn.
    stance: EvidenceStance | None = None

    quote: str | None = None

    # LLMClient.last_call for this source's call, when one was made.
    call: dict | None = None

    unreachable: bool = False


def prompt(article_block: str, claim: str, item: Evidence, excerpt: str) -> str:
    """
    The article and the claim first: one claim's calls share them, so
    after the first source Ollama finds them already read.
    """

    return f"{article_block}Claim:\n{claim}\n\nSource: {item.title} ({item.domain or item.url})\n{excerpt}"


def stance_of(answer) -> EvidenceStance | None:

    if not isinstance(answer, dict):
        return None

    return _STANCES.get(str(answer.get("stance", "")).strip().lower())


def verdict_from(answers: list[SourceAnswer], evidence: list[Evidence]) -> tuple[Verdict, float, list[int]]:
    """
    The rule in the module docstring. Outlets, not pages: five copies of
    one wire story are one source. The confidence says how much of the
    evidence agrees with the verdict - 0.5 with one source of five, 1.0
    with all five - and the scorer weighs it with the evidence's quality
    as it weighs the list verifier's own figure.
    """

    def outlets(stance: EvidenceStance) -> set[str]:
        return {
            evidence[answer.index].domain or evidence[answer.index].url
            for answer in answers
            if answer.stance == stance
        }

    supporting = outlets(EvidenceStance.SUPPORTS)
    contradicting = outlets(EvidenceStance.CONTRADICTS)

    cited = [
        answer.index for answer in answers
        if answer.stance in (EvidenceStance.SUPPORTS, EvidenceStance.CONTRADICTS)
    ]

    if not supporting and not contradicting:
        return Verdict.UNVERIFIED, 0.0, []

    every = len({item.domain or item.url for item in evidence}) or 1

    if len(contradicting) > len(supporting):
        return Verdict.FALSE, min(1.0, 0.5 + 0.5 * len(contradicting) / every), cited

    return Verdict.TRUE, min(1.0, 0.5 + 0.5 * len(supporting) / every), cited


_WORDS = {
    "en": ("states it", "states otherwise", "say nothing on it", "are about something else", "no source states it either way"),
    "es": ("lo afirma", "afirma otra cosa", "no dicen nada al respecto", "tratan de otra cosa", "ninguna fuente lo afirma ni lo niega"),
}


def explanation(answers: list[SourceAnswer], evidence: list[Evidence], language: str | None) -> str:
    """
    What the sources said, from their stances and checked quotes rather
    than from prose the model wrote: the explanation and the per-source
    list cannot tell different stories.
    """

    states, otherwise, silent, unrelated, nothing = _WORDS.get(language or "en", _WORDS["en"])

    parts = []

    for answer in answers:

        if answer.stance not in (EvidenceStance.SUPPORTS, EvidenceStance.CONTRADICTS):
            continue

        item = evidence[answer.index]
        verb = states if answer.stance == EvidenceStance.SUPPORTS else otherwise
        said = f': "{answer.quote}"' if answer.quote else ""

        parts.append(f"[{answer.index}] {item.domain or item.url} {verb}{said}")

    quiet = sum(1 for answer in answers if answer.stance == EvidenceStance.SILENT)
    off = sum(1 for answer in answers if answer.stance == EvidenceStance.UNRELATED)

    if not parts:
        parts.append(nothing)

    if quiet:
        parts.append(f"{quiet} {silent}")

    if off:
        parts.append(f"{off} {unrelated}")

    return "; ".join(parts) + "."


def merged_call(answers: list[SourceAnswer]) -> dict | None:
    """One claim's calls as the timing panel reads one call: summed."""

    calls = [answer.call for answer in answers if answer.call]

    if not calls:
        return None

    def total(name: str):
        values = [call.get(name) for call in calls if isinstance(call.get(name), (int, float))]
        return round(sum(values), 3) if values else None

    return {
        "model": calls[0].get("model"),
        "wait": total("wait"),
        "seconds": total("seconds"),
        "promptTokens": total("promptTokens"),
        "completionTokens": total("completionTokens"),
        "calls": len(calls),
    }
