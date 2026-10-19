#!/usr/bin/env python3
"""
Try a model as the reviewer: the draft review and its proposed
correction (`DraftReviewer`, src/services/corrector/draft_reviewer.py)
over the two drafts seeded with defects on 2026-10-15, against the model
server in LLM_BASE_URL - counted where a program can, printed for a
person where it cannot.

What is real and what is not
----------------------------

Real: `DraftReviewer` - both prompts, the call through `LLMClient`, the
grounding checks that bind the model's scores, the checks a proposal
must pass before a person is offered it - and the model.

Not: the drafts are the hand-written ones of 2026-10-15
(docs/decisions/writing.md, "Reviewing", Live) - the Catalan one as
test_the_first_live_catalan_proposal_is_not_offered keeps it, the
English one rebuilt from that record's description, since its text was
not kept - with two short sources each and two fact-checks; sentiment is a fixed stand-in (coverage is
not what is tried here, and inference/'s port is not published to the
host).

The defects planted, and what counts as finding one: an issue the
**model** raised (its raw answer, before the code's checks bind the
scores) that names it.

    en  "it's" for "its"           an issue quoting it's
    en  3 million where [1] says 1.2   an issue naming 3 million or 1.2
    en  the claim judged FALSE, stated uncited   an issue naming plastic
    en  an 8-character title, no subtitle   the model's title / subtitle scores
    ca  "esta" for "està"          an issue quoting esta
    ca  the claim judged FALSE, stated uncited   an issue naming plàstic(s)

Counted too: seconds and tokens per call, whether every metric parsed,
and whether the correction was offered or why it was not. For a person:
every issue the model raised - a problem it invented is a reading
(15 Oct: "the meadow's area is in no source", when [1] says it).

Usage (from backend/, so `src` and its virtualenv resolve):

    uv run python ../scripts/try_reviewer_model.py --model qwen3.5:4b
    uv run python ../scripts/try_reviewer_model.py --model llama3.2:3b --repeats 2 --json out.json

A hybrid reasoning model needs LLM_REASONING_EFFORT in the environment
(or backend/.env), as everywhere else. Nothing is stored but --json.
Measured 2026-10-15 with llama3.2:3b: it caught the FALSE claim in both
drafts and missed both spelling errors and the wrong figure.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from src.config.lexicons import writing_lexicon_for  # noqa: E402
from src.evaluation.usage import UsageMeter, metered, summarise  # noqa: E402
from src.models.nlp.sentiment_result import SentimentResult  # noqa: E402
from src.models.writer.draft import (  # noqa: E402
    ArticleDraft,
    DraftContent,
    DraftFactCheck,
    DraftRevision,
    DraftSource,
)
from src.services.corrector.draft_reviewer import REVIEW_LLM_KEYS, DraftReviewer, read_proposal  # noqa: E402
from src.services.corrector.text_corrector import UNAVAILABLE_SUMMARY, normalize_metric  # noqa: E402
from src.services.llms import LLMClient  # noqa: E402
from src.services.writer.draft_store import new_draft_id, now  # noqa: E402

# Coverage reads sentiment; what it says does not matter here.
NEUTRAL = SentimentResult(
    label="neutral",
    positive=0.34,
    neutral=0.33,
    negative=0.33,
    polarity=0.0,
    subjectivity=0.3,
    confidence=0.5,
    emotional_intensity=0.0,
)

FALSE_CLAIM = "The bay is now completely free of plastic pollution."

SOURCES = [
    DraftSource(
        url="https://example.org/posidonia-barceloneta",
        title="Ten years of seagrass replanting off Barceloneta",
        domain="example.org",
        origin="analysed",
        excerpt=(
            "Ten years after replanting began off Barceloneta beach, the restored Posidonia meadow covers "
            "4.2 hectares, twice its 2015 area. The city council funded the project with 1.2 million euros, "
            "and volunteers did most of the planting. Plastic waste remains a problem in the bay, the report says."
        ),
    ),
    DraftSource(
        url="https://example.com/juvenile-fish",
        title="Fish return to a restored meadow",
        domain="example.com",
        origin="related",
        excerpt="Divers counted 30% more juvenile fish in the restored meadow in 2025 than in 2020.",
    ),
]

FACT_CHECKS = [
    DraftFactCheck(claim="The restored meadow covers 4.2 hectares, twice its 2015 area.", verdict="TRUE", confidence=0.85),
    DraftFactCheck(claim=FALSE_CLAIM, verdict="FALSE", confidence=0.9),
]


@dataclass(frozen=True)
class Defect:

    name: str

    # Found when an issue the model raised matches this (case-insensitive).
    pattern: str


@dataclass(frozen=True)
class Seeded:

    language: str

    content: DraftContent

    defects: tuple[Defect, ...]


SEEDED = (
    Seeded(
        language="en",
        content=DraftContent(
            title="Seagrass",
            subtitle="",
            body=(
                "Off Barceloneta beach, ten years of replanting have brought the seagrass back. The restored "
                "meadow now covers 4.2 hectares, twice it's 2015 area [1].\n\n"
                "Divers counted 30% more juvenile fish in 2025 than in 2020 [2]. " + FALSE_CLAIM + "\n\n"
                "## Who made it possible\n\n"
                "The city council funded the project with 3 million euros [1], and volunteers did most of the "
                "planting."
            ),
        ),
        defects=(
            Defect("spelling: it's for its", r"it['’]s"),
            Defect("figure: 3 million where [1] says 1.2", r"3 million|\b1\.2\b"),
            Defect("the claim judged FALSE, stated", r"plastic"),
        ),
    ),
    Seeded(
        language="ca",
        content=DraftContent(
            title="La posidònia torna a la Barceloneta",
            subtitle="Deu anys de replantació han duplicat la praderia",
            body=(
                "Davant la platja de la Barceloneta, deu anys de replantació han fet tornar la posidònia. La "
                "praderia restaurada ja ocupa 4,2 hectàrees, el doble que el 2015 [1].\n\n"
                "Els bussejadors van comptar un 30% més de peixos joves el 2025 que el 2020 [2]. La badia ja esta "
                "completament lliure de contaminació per plàstics.\n\n"
                "## Qui ho ha fet possible\n\n"
                "L'Ajuntament va finançar el projecte amb 1,2 milions d'euros [1], i els voluntaris van fer la "
                "major part de la plantació."
            ),
        ),
        defects=(
            Defect("spelling: esta for està", r"\besta\b"),
            Defect("the claim judged FALSE, stated", r"pl[àa]stic"),
        ),
    ),
)


class Recording:
    """The client, keeping each parsed answer as the reviewer got it."""

    def __init__(self, llm: LLMClient):
        self.inner = llm
        self.model = llm.model
        self.answers: list = []

    def complete_json(self, *args, **kwargs):
        answer = self.inner.complete_json(*args, **kwargs)
        self.answers.append(answer)
        return answer


def draft_for(seeded: Seeded) -> ArticleDraft:

    stamp = now()

    return ArticleDraft(
        id=new_draft_id(),
        source_article_id="0123456789abcdef",
        language=seeded.language,
        instructions="Short, constructive, for a general audience.",
        content=seeded.content,
        sources=list(SOURCES),
        fact_checks=list(FACT_CHECKS),
        revisions=[DraftRevision(content=seeded.content, reason="generated", model="seeded", at=stamp)],
        model="seeded",
        created_at=stamp,
        updated_at=stamp,
    )


def review_once(model: str, timeout: float, seeded: Seeded) -> dict:

    meter = UsageMeter()
    llm = Recording(metered(LLMClient(model=model, timeout=timeout), meter))

    reviewer = DraftReviewer(llm=llm, sentiment_analyzer=_Fixed())
    draft = draft_for(seeded)

    started = time.monotonic()

    with meter.attribute() as calls:
        try:
            review = reviewer.review(draft)
            error = None
        except Exception as exc:  # the trial reports what a person would see fail
            review, error = None, f"{type(exc).__name__}: {exc}"

    seconds = time.monotonic() - started
    usage = summarise(calls)

    raw = llm.answers[0] if llm.answers else None
    model_metrics = {key: normalize_metric(raw, key) for key in REVIEW_LLM_KEYS}
    issues = [
        (key, issue)
        for key, metric in model_metrics.items()
        for issue in metric.issues
    ]

    found = {
        defect.name: any(re.search(defect.pattern, issue, re.IGNORECASE) for _, issue in issues)
        for defect in seeded.defects
    }

    proposal_reason = None

    if len(llm.answers) > 1:
        _, proposal_reason = read_proposal(llm.answers[1], draft.content, writing_lexicon_for(seeded.language))

    return {
        "language": seeded.language,
        "seconds": round(seconds, 1),
        "usage": {key: usage[key] for key in ("calls", "failedCalls", "promptTokens", "completionTokens", "latency")},
        "perCall": [round(call["latency"], 1) for call in usage["perCall"]],
        "error": error,
        "parsed": sum(1 for metric in model_metrics.values() if metric.summary != UNAVAILABLE_SUMMARY),
        "of": len(REVIEW_LLM_KEYS),
        "scores": {key: metric.score for key, metric in model_metrics.items()},
        "found": found,
        "issues": [f"{key}: {issue}" for key, issue in issues],
        "final": {key: metric.score for key, metric in review.metrics.items()} if review else None,
        "proposal": (
            "offered" if review and review.corrected is not None
            else "no answer" if len(llm.answers) < 2
            else f"not offered: {proposal_reason}"
        ),
        "corrected": review.corrected.model_dump() if review and review.corrected else None,
    }


class _Fixed:

    def process(self, text: str) -> SentimentResult:
        return NEUTRAL


def main() -> int:

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--model", required=True, help="the model name the server knows")
    parser.add_argument("--repeats", type=int, default=1, help="reviews of each draft (default 1)")
    parser.add_argument("--timeout", type=float, default=900.0, help="seconds per call (default 900)")
    parser.add_argument("--json", help="write every result to this file")
    args = parser.parse_args()

    results = []

    for repeat in range(args.repeats):
        for seeded in SEEDED:

            print(f"\n=== {args.model}, {seeded.language}, review {repeat + 1}", flush=True)

            result = review_once(args.model, args.timeout, seeded)
            results.append(result)

            usage = result["usage"]
            print(
                f"{result['seconds']} s; calls {result['perCall']} s; "
                f"tokens {usage['promptTokens']} in / {usage['completionTokens']} out; "
                f"metrics parsed {result['parsed']} of {result['of']}"
            )
            if result["error"]:
                print(f"FAILED: {result['error']}")
            print("model's scores: " + ", ".join(f"{key} {score:.0f}" for key, score in result["scores"].items()))
            for name, hit in result["found"].items():
                print(f"  {'FOUND ' if hit else 'missed'}  {name}")
            print(f"correction: {result['proposal']}")
            print("issues the model raised - read for invented ones:")
            for issue in result["issues"] or ["(none)"]:
                print(f"  - {issue}")

    defects = [(result["language"], name, hit) for result in results for name, hit in result["found"].items()]
    print(
        f"\n{args.model}: {sum(hit for *_, hit in defects)} of {len(defects)} planted defects found by the model; "
        f"corrections offered {sum(result['proposal'] == 'offered' for result in results)} of {len(results)}; "
        f"seconds per review {', '.join(str(result['seconds']) for result in results)}"
    )

    if args.json:
        Path(args.json).write_text(json.dumps({"model": args.model, "results": results}, indent=2, ensure_ascii=False), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
