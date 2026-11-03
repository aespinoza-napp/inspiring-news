---
name: verify
description: Choose and run the right ./scripts/check.sh targets for what changed in this repo, and report honestly what ran. Use after changing code, before saying work is done, or when asked to run the tests or checks.
---

# Verify a change

`./scripts/check.sh` is the definition of done. Never compose your own pytest or
tsc command for a final answer: the frontend is typechecked from another folder
and slow tests are excluded by a marker.

## Which target

| Changed | Run |
|---|---|
| Anything under `backend/` | `./scripts/check.sh` (backend, inference, typecheck, labeller) |
| Frontend pages, components, proxies | `./scripts/check.sh frontend`, then `e2e` |
| `labeller/` only | `./scripts/check.sh labeller` |
| Graph code | add `./scripts/check.sh graph` (fails if Neo4j is down) |
| `deploy/gcp/` | `./scripts/check.sh gcp` (Docker only) |
| Lake writes, lineage | add `./scripts/check.sh lake` (read-only) |
| Models, enrichment, the corpus | add `./scripts/check.sh slow` |

## Pitfalls that have cost time here

- **Model tests skip unless `inference/` runs on the host**, because port 8001 is
  not published. A green run with skips is not "passes with the models". To run them:
  `cd inference && uv run uvicorn src.main:app --port 8001`.
- **Never run `npm run build` in `frontend/` while `npm run dev` runs**: it replaces
  the dev server's `.next`. The `e2e` target builds into `.next-e2e` for this reason.
- **A timeout is not a failure.** Exit 143 means your own limit killed it. Run long
  targets in the background instead of guessing a limit.
- **Inference tests can fail once with a meta-tensor error** while the model warms
  up. Re-run before calling it a regression, and report that it happened.
- **Code running in Docker comes from the image.** After changing `backend/src`,
  rebuild it before testing through the stack (`scripts/stack.sh` sets `CODE_REVISION`).

## Reporting

Say which targets ran, the counts, what was skipped and why, and any failure that
went away on a re-run. Never summarise a run you did not read to the end.
