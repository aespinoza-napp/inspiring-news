"""
Was the web search answering about the claim, or about something else?

For each evaluation run (backend/data/evaluation/runs/**/results.jsonl):
how many web evidence candidates there were, the share whose title shares
a 5+ letter word with its claim, and the share from domains that only
show up when search has failed (arXiv, DOI, dictionaries, the bare word's
Wikipedia page). A count of results says nothing here: on 2026-11-03 Bing
answered every query with ten results about its first word only
(docs/fact-checking-changes.md, section 9). Full runs to 30 Oct read
65-70% and 0-11%.

    python scripts/evidence_on_subject.py [runs-glob]

Standard library only. A rough screen, not a measure of relevance: a
title can share a word and be off the subject.
"""

import collections
import glob
import json
import os
import re
import sys
from datetime import date

ROOT = os.path.join(os.path.dirname(__file__), "..", "backend", "data", "evaluation", "runs")

OFF_SUBJECT = {
    "arxiv.org", "doi.org", "dictionary.cambridge.org", "wordreference.com",
    "collinsdictionary.com", "merriam-webster.com", "southpark.cc.com",
}


def words(text: str | None) -> set[str]:
    return set(re.findall(r"[^\W\d_]{5,}", (text or "").lower()))


def main(pattern: str) -> None:
    for path in sorted(glob.glob(pattern, recursive=True), key=os.path.getmtime):
        rows = []
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue

        web = [(row, item) for row in rows for item in row.get("candidates") or [] if item.get("origin") == "web"]
        if not web:
            continue

        shared = sum(1 for row, item in web if words(row.get("claim")) & words(item.get("title")))
        off = sum(1 for _, item in web if item.get("domain") in OFF_SUBJECT)
        top = collections.Counter(item.get("domain") for _, item in web).most_common(3)

        run = os.path.relpath(os.path.dirname(path), ROOT)
        print(
            f"{run:48s} {date.fromtimestamp(os.path.getmtime(path))}  claims {len(rows):3d}  web {len(web):4d}  "
            f"share a claim word {shared / len(web):4.0%}  off-subject domains {off / len(web):4.0%}  top {top}"
        )


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "**", "results.jsonl"))
