---
name: commit
description: Commit this repository's uncommitted work as reviewable, verified commits on the current branch. Use only when the user asks to commit.
disable-model-invocation: true
---

# Commit the work

## Before anything

1. `git status --short` and `git diff --stat HEAD`. Read what is there: not everything
   is yours. Files you did not change stay out unless the user says otherwise.
2. On `main`, branch first. Work normally goes on `dev`.
3. Run the `verify` skill. If it fails, stop and say so.

## Split it

One commit per change someone could review or revert alone, in an order where each one
passes. A code change travels with its tests and the documents describing it.

Stage named paths. **Never `git add -A` or `git add .`.** Check the staged list for
anything secret or generated:

```bash
git diff --cached --name-only
```

`backend/.env`, any `.env.*` copy, `data/lake/` and `evaluation/runs/` must never appear.

## The message

The title says what changed, as the log does, not that something was done: "Verifier: one
source at a time, by majority, is the default", never "added basic commit" or "fix". Use a
body when the reason is not obvious, and include measured numbers when a change affects
verdicts. End with the attribution lines this session specifies, if any. Never skip hooks
or amend a pushed commit.

## Afterwards

Show `git log --oneline` for the new commits and `git status --short`. Do not push
unless the user asked in this conversation. Pushing runs CI, so say which jobs are new or
have never run.
