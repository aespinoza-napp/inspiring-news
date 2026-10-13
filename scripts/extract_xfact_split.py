#!/usr/bin/env python3
"""
One language's rows of one X-Fact split, out of the filtered set, as a
dataset of its own for the evaluation harness.

    python scripts/extract_xfact_split.py backend/data/evaluation/xfact_en_es.jsonl \
        es test backend/data/evaluation/xfact_es_test.jsonl

Written for the Spanish `test` split (165 claims, all chequeado.com):
X-Fact's in-domain test set, alpha-1, restricted to the one language of
it this project covers. The closest thing we have to the set the X-Fact
paper's Table 3 reports on (docs/decisions/xfact-comparison.md).

Deterministic: the source's lines, in the source's order, byte for byte.
Nothing is parsed back into a new line, so a row here is the row in
xfact_en_es.jsonl and its harness id (sha1 of language, site and claim)
is the one it would have there.

Standard library only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def extract(source: Path, language: str, split: str) -> list[str]:

    kept = []

    with source.open(encoding="utf-8", newline="") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("language") == language and row.get("split") == split:
                kept.append(line if line.endswith("\n") else line + "\n")

    return kept


def main() -> int:

    if len(sys.argv) != 5:
        print(__doc__)
        return 2

    source, language, split, target = Path(sys.argv[1]), sys.argv[2], sys.argv[3], Path(sys.argv[4])

    lines = extract(source, language, split)

    if not lines:
        print(f"no {language} rows in split {split!r} of {source}", file=sys.stderr)
        return 1

    target.parent.mkdir(parents=True, exist_ok=True)

    with target.open("w", encoding="utf-8", newline="") as f:
        f.writelines(lines)

    labels: dict[str, int] = {}
    for line in lines:
        label = json.loads(line)["label"]
        labels[label] = labels.get(label, 0) + 1

    print(f"Wrote {len(lines)} {language}/{split} rows to {target}")
    print(f"By label: {dict(sorted(labels.items()))}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
