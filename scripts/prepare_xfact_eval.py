#!/usr/bin/env python3
"""
Filters the X-Fact dataset (Gupta & Srikumar, 2021) down to English and
Spanish, and maps its 7-class label taxonomy onto this project's Verdict
enum, for the Phase 4 benchmark ground-truth set the roadmap flags as
missing (docs/roadmap.md, "Also this sprint" / docs/decisions - Phase 4
is 140h of benchmarking with nothing to benchmark against).

X-Fact was chosen over FEVER precisely because it is an open-retrieval
benchmark (see docs/final_document/sections/evaluation_dataset.tex):
its claims are real-world statements verified against the open web, not
against a closed corpus, which matches this pipeline's own architecture.

Source: https://github.com/utahnlp/x-fact (data/x-fact-including-en/).
That variant is used, not the base x-fact/ one, because English claims
only exist there - X-Fact's real held-out languages are the other 24;
English was added as a training-time augmentation, which is also why it
has no dev/test split of its own (see the "only in train" note below).

Usage:
    git clone --depth 1 https://github.com/utahnlp/x-fact.git /tmp/x-fact-src
    python scripts/prepare_xfact_eval.py /tmp/x-fact-src/data/x-fact-including-en \
        backend/data/evaluation/xfact_en_es.jsonl
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

# X-Fact's coarse 7-class taxonomy (data/x-fact/label_maps/master_mapping.tsv)
# mapped onto this project's 5-value Verdict enum
# (src/models/fact_checker/fact_check.py). There is no clean bijection -
# X-Fact distinguishes "mostly true"/"mostly false" from the absolutes and
# this project does not - so this mapping is a documented judgement call,
# not a fact:
#
#   true                        -> TRUE
#   mostly true                 -> PARTIALLY_TRUE (central claim holds, a
#                                  detail does not - our own definition of
#                                  PARTIALLY_TRUE)
#   partly true/misleading      -> MISLEADING (X-Fact's own label already
#                                  names this "misleading")
#   mostly false                -> FALSE (leans false; there is no
#                                  intermediate bucket on the false side)
#   false                       -> FALSE
#   complicated/hard to categorise -> UNVERIFIED (X-Fact's own examples for
#                                  this bucket are "unverifiable",
#                                  "not proven", "cannot be checked")
#   other                       -> dropped (satire, corrections, etc. -
#                                  not a verdict on the claim's truth)
LABEL_MAP = {
    "true": "TRUE",
    "mostly true": "PARTIALLY_TRUE",
    "partly true/misleading": "MISLEADING",
    "mostly false": "FALSE",
    "false": "FALSE",
    "complicated/hard to categorise": "UNVERIFIED",
    # English rows in this dataset keep PolitiFact's own native scale
    # rather than the master-mapped label the other languages already
    # carry (see master_mapping.tsv - "half true" is one of the raw
    # labels it folds into "partly true/misleading" for everyone else).
    # There is no English equivalent of "complicated/hard to categorise"
    # in PolitiFact's scale, so en genuinely has no UNVERIFIED claims
    # here - not a bug in this mapping, a property of the source data.
    "half true": "PARTIALLY_TRUE",
}
DROPPED_LABELS = {"other"}

LANGUAGES = {"en", "es"}

# English only exists in train.all.tsv in this dataset (see this script's
# module docstring) - dev/test only carry the real held-out languages,
# Spanish among them. Read every split for es; only train for en.
SPLITS_BY_LANGUAGE = {
    "es": ["train.all.tsv", "dev.all.tsv", "test.all.tsv"],
    "en": ["train.all.tsv"],
}


def read_split(path: Path, language: str) -> list[dict]:

    rows = []

    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")

        for row in reader:

            if row.get("language") != language:
                continue

            label_raw = (row.get("label") or "").strip().lower()

            if label_raw in DROPPED_LABELS or label_raw not in LABEL_MAP:
                continue

            evidence_links = [
                row[key] for key in ("link_1", "link_2", "link_3", "link_4", "link_5")
                if row.get(key) and row[key] not in ("none", "NO_LINK")
            ]

            rows.append({
                "language": language,
                "site": row.get("site"),
                "claimant": row.get("claimant") or None,
                "claim": row.get("claim", "").strip(),
                "claimDate": row.get("claimDate") or None,
                "reviewDate": row.get("reviewDate") or None,
                "labelRaw": label_raw,
                "label": LABEL_MAP[label_raw],
                # Reference-only: this project does open-domain retrieval
                # (SearXNG at verification time), so these are not fed to
                # the pipeline as evidence - they're X-Fact's own sources,
                # kept for manual spot-checking a disagreement.
                "referenceEvidenceLinks": evidence_links,
                "split": path.stem.replace(".all", ""),
            })

    return rows


def main() -> int:

    if len(sys.argv) != 3:
        print(__doc__)
        return 2

    src_dir = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    all_rows: list[dict] = []

    for language, splits in SPLITS_BY_LANGUAGE.items():
        for split in splits:
            path = src_dir / split
            if not path.exists():
                print(f"skip (missing): {path}", file=sys.stderr)
                continue
            rows = read_split(path, language)
            all_rows.extend(rows)
            print(f"{language} / {split}: {len(rows)} claims kept")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as f:
        for row in all_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    by_lang: dict[str, int] = {}
    by_label: dict[str, int] = {}

    for row in all_rows:
        by_lang[row["language"]] = by_lang.get(row["language"], 0) + 1
        by_label[row["label"]] = by_label.get(row["label"], 0) + 1

    print(f"\nWrote {len(all_rows)} claims to {out_path}")
    print(f"By language: {by_lang}")
    print(f"By mapped label: {by_label}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
