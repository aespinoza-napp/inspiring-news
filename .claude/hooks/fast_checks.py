#!/usr/bin/env python3
"""
PostToolUse hook: after an edit under backend/src or backend/tests, run the
invariants (./scripts/check.sh fast, seconds, no models).

Replaces a one-liner that read $CLAUDE_FILE_PATHS: hooks are handed their data
as JSON on stdin, so on that input it did nothing and said nothing (found
2026-11-03). A failure exits 2, which shows Claude the output; anything else
that goes wrong stays out of the way of the edit.
"""

import json
import os
import subprocess
import sys

WATCHED = ("backend/src/", "backend/tests/")

# The end of the output is where pytest says what failed.
TAIL_CHARS = 3000


def main() -> int:

    payload = json.load(sys.stdin)

    root = os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".")
    path = (payload.get("tool_input") or {}).get("file_path") or ""

    relative = os.path.relpath(os.path.realpath(path), root).replace(os.sep, "/") if path else ""

    if not relative.startswith(WATCHED):
        return 0

    result = subprocess.run(
        ["bash", "scripts/check.sh", "fast"],
        cwd=root, capture_output=True, text=True, timeout=110,
    )

    if result.returncode == 0:
        return 0

    print(f"./scripts/check.sh fast failed after editing {relative}:\n{(result.stdout + result.stderr)[-TAIL_CHARS:]}", file=sys.stderr)

    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
