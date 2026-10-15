#!/usr/bin/env python3
"""
Try a model as the writer: one real draft per language from a committed
sample article, against the model server in LLM_BASE_URL, and the four
things that decided against llama3.2:3b (docs/decisions/writing.md,
"The model") - counted where a program can, printed for a person where
it cannot.

What is real and what is not
----------------------------

Real: `ArticleWriter` - the prompt, the fitting to the budget, the call
through `LLMClient` (and its warning when the server cut the prompt),
the checks and repairs of `draft_checks.py` - and the model.

Not: the analysed article is a committed sample
(`backend/data/processed/`, CNN on lithium in drinking water and
autism), not a lake record; its fact-checks are written here, one
TRUE, one UNVERIFIED and one planted FALSE; there is no related news
and no evidence page, as when both routes fail. So this measures the
model's writing under the rules, not the search.

Counted: time; citations; sentences without one; whether metadata came
back; whether the server cut the prompt. For a person: the article, and
the claims it was told not to state - whether it did is a reading, and
so is the quality of the Catalan.

Usage (from backend/, so `src` and its virtualenv resolve):

    uv run python ../scripts/try_writer_model.py --model qwen2.5:7b-instruct
    uv run python ../scripts/try_writer_model.py --model writer --language ca

Nothing is stored. Measured 2026-10-15 with llama3.2:3b: no citation in
four drafts, the UNVERIFIED claim stated in three.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from src.config.thresholds import WriterThresholds  # noqa: E402
from src.services.llms import LLMClient  # noqa: E402
from src.services.writer.analysed_article import AnalysedArticle, CheckedClaim  # noqa: E402
from src.services.writer.article_writer import (  # noqa: E402
    NOT_TO_STATE,
    SYSTEM_PROMPT,
    ArticleWriter,
    WriterError,
    user_prompt,
)
from src.services.writer.draft_checks import CITATION, uncited_sentences  # noqa: E402
from src.services.writer.draft_writer import build_fact_checks, build_sources  # noqa: E402

SAMPLE = Path("data/processed/2026-07-30_cnn_ab04fb5724674191a32fdfbffe642523.json")

NOTE = "Web search was unavailable, so no news from the web could be looked for."


def sample_article() -> AnalysedArticle:

    record = json.loads(SAMPLE.read_text(encoding="utf-8"))

    # The committed sample carries U+FFFD where its apostrophes were.
    body = record["body"].replace("�", "'")

    return AnalysedArticle(
        id="0123456789abcdef",
        url=record["url"],
        headline="Lithium in drinking water linked to a modestly higher autism risk, Danish study finds",
        lead=body[:500],
        language="en",
        topic="Health",
        published_at="2023-04-03T00:00:00",
        source_name="CNN",
        domain="cnn.com",
        claims=(
            CheckedClaim(
                text=(
                    "Compared with the lowest exposure, the second and third highest exposure during "
                    "pregnancy had a 24% to 26% higher risk of an autism diagnosis."
                ),
                verdict="TRUE",
                confidence=0.84,
            ),
            CheckedClaim(
                text=(
                    "Autism diagnosis rates tripled among certain age groups in the New York-New Jersey "
                    "area between 2000 and 2016."
                ),
                verdict="UNVERIFIED",
                confidence=0.5,
            ),
            # Planted: the article says the opposite.
            CheckedClaim(text="Lithium in tap water causes autism.", verdict="FALSE", confidence=0.9),
        ),
        body=body,
    )


def main() -> int:

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--model", required=True, help="the model name the server knows")
    parser.add_argument("--language", choices=["ca", "es", "en"], action="append", help="repeatable; default ca and es")
    parser.add_argument("--timeout", type=float, default=900.0, help="seconds per draft (default 900)")
    parser.add_argument("--instructions", default="", help="the editor's indications")
    args = parser.parse_args()

    article = sample_article()
    writer = ArticleWriter(LLMClient(model=args.model, timeout=args.timeout))
    thresholds = WriterThresholds()
    fact_checks = build_fact_checks(article)

    withheld = [check.claim for check in fact_checks if check.verdict in NOT_TO_STATE]

    for language in args.language or ["ca", "es"]:

        sources = writer.fit(
            article, build_sources(article, [], thresholds), fact_checks, language, args.instructions, [NOTE], thresholds
        )

        size = len(SYSTEM_PROMPT) + len(user_prompt(article, sources, fact_checks, language, args.instructions, [NOTE]))

        print(f"\n=== {args.model}, {language}: {size:,} prompt characters")

        started = time.monotonic()

        try:
            written = writer.write(article, sources, fact_checks, language, args.instructions, [NOTE], thresholds)
        except WriterError as exc:
            print(f"FAILED after {time.monotonic() - started:.0f} s: {exc}")
            continue

        body = written.content.body
        metadata = written.metadata

        print(f"{time.monotonic() - started:.0f} s")
        print(f"citations: {len(CITATION.findall(body))}; sentences without one: {len(uncited_sentences(body))}")
        print(
            "metadata: "
            + ", ".join(
                f"{name} {'yes' if value else 'MISSING'}"
                for name, value in (
                    ("SEO description", metadata.seo_description),
                    ("keywords", metadata.keywords),
                    ("tags", metadata.tags),
                )
            )
        )
        for finding in written.findings:
            print(f"finding: {finding}")

        print(f"\n# {written.content.title}\n{written.content.subtitle}\n\n{body}\n")
        print("Told not to state as fact - check the text above:")
        for claim in withheld:
            print(f"  - {claim}")

    print("\nA warning above that the server 'probably cut' the prompt means its context is too small.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
