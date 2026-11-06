#!/usr/bin/env python3
"""
PreToolUse hook for the troubleshooting agent (backend/src/evaluation/troubleshoot.py).

It does nothing unless TROUBLESHOOT_PHASE is set, which only the script sets,
on the `claude -p` sessions it starts. Then:

- **plan / search (blind):** Claude writes what it would look for, and what it
  found, before it can see a label or a pipeline record - the 4 Nov protocol
  (docs/troubleshooting/fact-checking/README.md). Refused: the run records,
  the label files, the earlier comparison, the troubleshooting docs (they
  quote the pipeline's queries), the batch's stage directories (pipeline and
  comparison files), any write outside the batch directory, and a WebFetch of
  one of the batch's own articles' sites.
- **analyse / implement:** the numbers are the script's. Refused: editing the
  batch's claims, plan, claude, pipeline, comparison and metrics files, and
  the experiment file's measured section is checked by the script on its
  next write (it rewrites it). Writes go to the batch, the troubleshooting
  docs, and with `implement` backend/src and backend/tests only.

Against accident and drift, not against intent: the author can read every
step in the batch's logs/. Exit 2 shows Claude why; a fault in the hook lets
the call through rather than break the session.
"""

import json
import os
import re
import sys
from urllib.parse import urlparse

BLIND = ("plan", "search")

# What a blind phase must not read: run records (labels, queries, stances),
# label files, the 4 Nov comparison, the docs that quote the pipeline.
BLIND_TOKENS = (
    "data/evaluation/runs",
    "evaluation/manual",
    "custom_en_es",
    "experiments/claude-search",
    "experiments/iterate",
    "docs/troubleshooting",
    "comparison",
    "metrics-",
    "pipeline-",
    "results.jsonl",
    "evidence.jsonl",
    "fact-checking-changes",
    "docs/audit",
)

# Files only the script writes.
MEASURED = re.compile(r"(?:^|/)(?:claims\.jsonl|plan\.jsonl|claude\.jsonl|batch\.json|pipeline-[^/]*|comparison-[^/]*|metrics-[^/]*|try\.json)$")


def norm(path: str, root: str) -> str:

    path = (path or "").replace("\\", "/")

    if path and not path.startswith("/"):
        path = os.path.normpath(os.path.join(root, path)).replace("\\", "/")

    return os.path.normpath(path).replace("\\", "/") if path else ""


def article_hosts(batch: str) -> set[str]:

    hosts = set()

    try:
        with open(os.path.join(batch, "claims.jsonl"), encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    host = (urlparse(json.loads(line).get("articleUrl") or "").hostname or "").lower()
                    if host:
                        hosts.add(host[4:] if host.startswith("www.") else host)
    except (OSError, ValueError):
        pass

    return hosts


PROTECTED = (
    "backend/src/evaluation/troubleshoot.py",
    "backend/tests/evaluation/test_troubleshoot.py",
    ".claude/hooks/troubleshoot_blind.py",
)


def held_out(root: str, tool: str, tool_input: dict) -> str | None:
    """
    In a loop round (TROUBLESHOOT_HOLDOUT set), the held-out batch is
    measured by the script and never read by the agent: a change written
    after seeing it would be judged on what it was fitted to. A search over
    a directory that holds it reads it too.
    """

    holdout = os.environ.get("TROUBLESHOOT_HOLDOUT")

    if not holdout:
        return None

    holdout = norm(holdout, root)
    target = norm(tool_input.get("file_path") or tool_input.get("path") or "", root)
    text = " ".join(str(tool_input.get(key) or "") for key in ("file_path", "path", "pattern", "glob", "command"))

    if os.path.basename(holdout) in text or (target and (target == holdout or target.startswith(holdout + "/"))):
        return "the held-out batch is the loop's, never the agent's"

    if tool in ("Grep", "Glob") and (not target or holdout.startswith(target.rstrip("/") + "/")):
        return "a search over a directory holding the held-out batch reads it; name a path inside the tune batch or the code"

    return None


def refusal(phase: str, batch: str, root: str, tool: str, tool_input: dict) -> str | None:

    batch = norm(batch, root)

    if tool in ("Write", "Edit", "NotebookEdit"):

        path = norm(tool_input.get("file_path") or tool_input.get("notebook_path") or "", root)

        if phase in BLIND:
            allowed = path in (f"{batch}/plan.jsonl", f"{batch}/claude.jsonl") if phase == "search" else path == f"{batch}/plan.jsonl"
            if phase == "search" and path == f"{batch}/plan.jsonl":
                return "the plan is written before the search and is not changed by it"
            return None if allowed else f"a {phase} step writes only its own file in {batch}"

        if MEASURED.search(path):
            return f"{os.path.basename(path)} is measured or blind evidence, written only by the script"

        # The measure itself: an agent that could edit how a round is counted
        # could pass any round. A new planning threshold goes through
        # query_builder.plan_arguments instead, which the measure calls.
        if path in (norm(name, root) for name in PROTECTED):
            return f"{os.path.relpath(path, root)} is how the loop measures and decides; the agent may not change it"

        holdout = os.environ.get("TROUBLESHOOT_HOLDOUT")

        if holdout and path.startswith(norm(holdout, root) + "/"):
            return "the held-out batch is the loop's, never the agent's"

        allowed = [batch + "/", f"{norm('docs/troubleshooting', root)}/"]

        if phase == "implement":
            allowed += [f"{norm('backend/src', root)}/", f"{norm('backend/tests', root)}/"]

        if not any(path.startswith(prefix) for prefix in allowed):
            return f"{phase} writes only under {', '.join(allowed)}"

        return None

    if phase not in BLIND:
        return held_out(root, tool, tool_input)

    if tool == "WebFetch":
        host = (urlparse(tool_input.get("url") or "").hostname or "").lower()
        host = host[4:] if host.startswith("www.") else host
        for site in article_hosts(batch):
            if host == site or host.endswith("." + site):
                return f"{host} is the article being checked; it cannot corroborate itself"
        return None

    if tool == "Bash":
        return "no shell in a blind step"

    # A search over a directory reads every file in it, records included.
    if tool == "Grep":
        return "no content search in a blind step"

    text = " ".join(str(tool_input.get(key) or "") for key in ("file_path", "path", "pattern", "glob")).replace("\\", "/")
    target = norm(tool_input.get("file_path") or tool_input.get("path") or "", root)

    for token in BLIND_TOKENS:
        if token in text or token in target:
            return f"`{token}` holds labels or the pipeline's side; the {phase} step is blind"

    own = {f"{batch}/{name}" for name in ("claims.jsonl", "plan.jsonl", "claude.jsonl")}

    # Of the data, only the claims and Claude's own files: every other file
    # under backend/data may carry a label, a query or a verdict.
    if tool == "Read" and target.startswith(norm("backend/data", root) + "/") and target not in own:
        return "of backend/data, a blind step reads only its batch's claims and its own files"

    if target.startswith(batch + "/") and target not in own and tool == "Read":
        return "the batch's stage files are the pipeline's side; the step is blind"

    return None


def main() -> int:

    phase = os.environ.get("TROUBLESHOOT_PHASE")
    batch = os.environ.get("TROUBLESHOOT_BATCH")

    if not phase or not batch:
        return 0

    payload = json.load(sys.stdin)
    root = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or "."

    reason = refusal(phase, batch, root, payload.get("tool_name") or "", payload.get("tool_input") or {})

    if reason is None:
        return 0

    print(f"Refused ({phase} step of the troubleshooting agent): {reason}.", file=sys.stderr)

    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
