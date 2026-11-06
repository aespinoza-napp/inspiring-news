#!/usr/bin/env python3
"""
PreToolUse hook: while an iteration campaign is active
(backend/data/evaluation/experiments/iterate/*/campaign.json, "status":
"active"), keep the agent away from the custom set's test half.

The campaign tunes on the train half; the test half decides once, at the
end, run by the author (docs/decisions/evaluation.md, "The split" and "The
iteration loop"). A change designed after reading test claims cannot be
judged on them - V4 was, and had to be judged on train instead. This
guards against accident, not against a determined agent: `iterate close`
ends the campaign, and ITERATE_ALLOW_TEST_HALF=1 in the session's
environment lets the author through.

Refused while a campaign is active:
- a harness `run` that is not `--split train`, unless it is over AVeriTeC;
- anything naming the test half's runs or reports (`manual-test`), its
  split (`--split test`), or the labels themselves (`custom_en_es.jsonl`,
  a fact file under `data/evaluation/manual/`). A train run's records carry
  their own labels, which is all a diagnosis needs.

Exit 2 shows Claude why; anything that goes wrong in the hook itself lets
the call through rather than block the session.
"""

import glob
import json
import os
import re
import sys

CAMPAIGNS = "backend/data/evaluation/experiments/iterate/*/campaign.json"

# The harness's own dataset argument names the directory, not a file in it.
ALLOWED_DATASET = re.compile(r"--dataset\s+(?:\S*/)?data/evaluation/manual(?=\s|$)")

# AVeriTeC is not the custom set: its dev split is public, is the split published
# figures are reported on, and shares no claim with the half sealed here.
# Exempted at the author's choice, 2026-11-05 (src/evaluation/averitec.py).
AVERITEC_DATASET = re.compile(r"--dataset\s+(?:\S*/)?data/evaluation/averitec/averitec_(?:dev|train)\.jsonl(?=\s|$)")

TOKENS = ("manual-test", "--split test", "--split=test", "custom_en_es.jsonl", "evaluation/manual/")


def active(root: str) -> list[str]:

    names = []

    for path in glob.glob(os.path.join(root, CAMPAIGNS)):
        try:
            with open(path, encoding="utf-8") as handle:
                if json.load(handle).get("status") == "active":
                    names.append(os.path.basename(os.path.dirname(path)))
        except (OSError, ValueError):
            continue

    return names


def refusal(tool: str, tool_input: dict) -> str | None:

    if tool == "Bash":

        command = tool_input.get("command") or ""

        # The module invoked, not its name mentioned: `pgrep -f "src.evaluation.cli run"`
        # checking on a run was refused by the first version (2026-11-04).
        if (
            re.search(r"-m\s+src\.evaluation\.cli\s+run\b", command)
            and "--split train" not in command
            and not AVERITEC_DATASET.search(command)
        ):
            return "a harness run must be `--split train` during a campaign"

        text = ALLOWED_DATASET.sub("--dataset <train>", command)

    else:
        text = " ".join(str(tool_input.get(key) or "") for key in ("file_path", "path", "pattern", "glob"))

    for token in TOKENS:
        if token in text.replace("\\", "/"):
            return f"`{token}` is the test half or its labels"

    return None


def main() -> int:

    if os.environ.get("ITERATE_ALLOW_TEST_HALF") == "1":
        return 0

    payload = json.load(sys.stdin)

    root = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or "."

    campaigns = active(root)

    if not campaigns:
        return 0

    reason = refusal(payload.get("tool_name") or "", payload.get("tool_input") or {})

    if reason is None:
        return 0

    print(
        f"Refused: {reason}, and the iteration campaign {', '.join(campaigns)} is active. "
        "The test half is the author's, once, after the campaign is closed "
        "(`cli iterate close`). Work from the train half's run records instead.",
        file=sys.stderr,
    )

    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
