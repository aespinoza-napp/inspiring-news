"""
The checks an article written by hand goes through before anyone reads it:
the same ones the app runs on the writer model's answer (draft_checks.py)
and on every review (corrector/grounding.py), against the draft's own
numbered sources and fact-checks.

    cd backend && uv run python ../scripts/check_article.py \
        --draft <draft.json> --article <article.md>

Used by both writing skills, /write-constructive-article and
/write-devastating-article (.claude/skills/): the checks are the same in
both editions, the voice is not.

<draft.json> is GET /drafts/{id} as saved (or the file under
DRAFTS_PATH); <article.md> starts with "# Title", then the subtitle on its
own line, then the Markdown body citing [n]. Prints JSON: words, parts,
what was repaired, every uncited, unsupported or dangling sentence, and
every sentence repeating a claim the fact-check did not confirm (a
Devastating draft has no fact-checks: its edition is not checked), and,
for a Devastating story touching suicide or self-harm, the safe-messaging
line the newsroom appends - never written by hand. Nothing is written
anywhere.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from src.config.lexicons import writing_lexicon_for  # noqa: E402
from src.models.writer.draft import ArticleDraft  # noqa: E402
from src.services.corrector import grounding  # noqa: E402
from src.services.writer.article_writer import ARTICLE_PARTS, ARTICLE_WORDS, with_safe_messaging  # noqa: E402
from src.services.writer.draft_checks import check  # noqa: E402


def read_article(path: Path) -> tuple[str, str, str]:

    lines = path.read_text(encoding="utf-8").strip().splitlines()

    if not lines or not lines[0].startswith("# "):
        raise SystemExit(f"{path}: the first line must be '# Title'")

    title = lines[0][2:].strip()

    rest = [line for line in lines[1:]]

    while rest and not rest[0].strip():
        rest.pop(0)

    subtitle = rest.pop(0).strip() if rest and not rest[0].startswith("#") else ""

    return title, subtitle, "\n".join(rest).strip()


def main() -> None:

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--draft", type=Path, required=True)
    parser.add_argument("--article", type=Path, required=True)
    args = parser.parse_args()

    draft = ArticleDraft.model_validate(json.loads(args.draft.read_text(encoding="utf-8")))

    title, subtitle, body = read_article(args.article)

    sources = draft.sources
    analysed = next((source.excerpt for source in sources if source.origin == "analysed"), None)

    checked = check(
        body,
        title,
        len(sources),
        original=analysed,
        texts=[source.excerpt for source in sources]
        + [fact_check.claim for fact_check in draft.fact_checks]
        + [title],
    )

    found = grounding.check(
        checked.body,
        len(sources),
        draft.fact_checks,
        writing_lexicon_for(draft.language),
        sources={number: source.excerpt for number, source in enumerate(sources, start=1)},
    )

    words = len(re.findall(r"\w+", grounding.plain(checked.body)))

    report = {
        "title": title,
        "titleChars": len(title),
        "subtitle": subtitle,
        "words": words,
        "subheadings": re.findall(r"^## (.+)$", checked.body, flags=re.MULTILINE),
        "edition": draft.edition,
        # The five parts are the constructive edition's; the Devastating
        # one has no set parts (DEVASTATING_NEWSROOM).
        "partsExpected": [name for name, _ in ARTICLE_PARTS] if draft.edition == "positive" else None,
        "wordsExpected": ARTICLE_WORDS if draft.edition == "positive" else "400 to 700",
        "factChecks": len(draft.fact_checks),
        "repairedBody": checked.body != body,
        "findings": checked.findings,
        "factualSentences": found.factual,
        "uncited": found.uncited,
        "unsupported": found.unsupported,
        "uncitedButInSource": [{"sentence": sentence, "source": number} for sentence, number in found.uncited_present],
        "dangling": [{"sentence": sentence, "cites": number} for sentence, number in found.dangling],
        "repeatsUnconfirmedClaim": [
            {"sentence": echo.sentence, "claim": echo.claim, "verdict": echo.verdict} for echo in found.echoes
        ],
    }

    appended = with_safe_messaging(checked.body, draft.language, draft.edition, title, analysed)

    report["safeMessaging"] = appended[len(checked.body):].strip() or None

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
