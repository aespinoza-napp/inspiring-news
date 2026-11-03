#!/usr/bin/env python3
"""
Stop hook: uncommitted work is never left unsaid.

When Claude finishes with changes git does not hold and its last message does
not mention committing, it is sent back once to say so. It never commits: that
stays the author's call. Standard library only; anything unexpected lets Claude
stop, since a broken check must not trap a session.
"""

import json
import os
import re
import subprocess
import sys

# Any mention counts: "nothing is committed", "commit this?", "sin commitear".
MENTIONED = re.compile(r"commit|comit", re.IGNORECASE)

MAX_LISTED = 10

# A long transcript's end is all that is needed.
TAIL_BYTES = 262_144


def last_message_from_transcript(path: str | None) -> str:
    """For versions whose Stop input has no `last_assistant_message`."""

    if not path or not os.path.exists(path):
        return ""

    with open(path, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        handle.seek(max(0, handle.tell() - TAIL_BYTES))
        lines = handle.read().decode("utf-8", errors="replace").splitlines()

    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue

        if entry.get("type") != "assistant":
            continue

        content = (entry.get("message") or {}).get("content")
        text = content if isinstance(content, str) else " ".join(
            block.get("text", "") for block in content or [] if isinstance(block, dict)
        )

        if text.strip():
            return text

    return ""


def uncommitted(cwd: str) -> list[str]:

    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=cwd, capture_output=True, text=True, timeout=10, check=True,
    )

    return [line for line in result.stdout.splitlines() if line.strip()]


def main() -> int:

    payload = json.load(sys.stdin)

    # Already sent back once: say it and stop, never a loop.
    if payload.get("stop_hook_active"):
        return 0

    changes = uncommitted(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".")

    if not changes:
        return 0

    said = payload.get("last_assistant_message") or last_message_from_transcript(payload.get("transcript_path"))

    if MENTIONED.search(said or ""):
        return 0

    listed = "\n".join(changes[:MAX_LISTED])
    more = f"\n... and {len(changes) - MAX_LISTED} more" if len(changes) > MAX_LISTED else ""

    print(json.dumps({
        "decision": "block",
        "reason": (
            f"{len(changes)} path(s) are uncommitted and your last message does not say so:\n"
            f"{listed}{more}\n"
            "Tell the user in one or two sentences what is uncommitted. Do not commit "
            "unless they asked for it."
        ),
    }))

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
