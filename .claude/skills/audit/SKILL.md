---
name: audit
description: Run a scored engineering audit of this repository in the established format, on the same nine weighted dimensions as every earlier audit, and write it up. Use only when the user asks for an audit.
disable-model-invocation: true
---

# Audit the project

Earlier audits are `docs/audit-*.md`. Read the latest first, and re-check every open
finding against the code, not against what it says. Do not adjust earlier scores.

## Run everything you can

`./scripts/check.sh` with `inference/` running on the host, so model tests do not skip,
then `slow`, `graph`, `gcp`, `e2e` and `lake`. Whatever does not run is listed as not
run, with the reason. Run real articles through the stack if it is up.

Recompute the figures you quote: labels unreviewed (`grep -l 'not yet checked'
backend/data/evaluation/manual/*`), placeholders (`\pending{` in `docs/final_document`),
what is uncommitted and unmerged, and run health (`scripts/evidence_on_subject.py`).

## Score

Same dimensions and weights every time, so the series stays comparable:

| Dimension | Weight |
|---|---|
| Correctness & data integrity | 20% |
| Multilingual correctness | 15% |
| Architecture & boundaries | 15% |
| Test quality | 15% |
| Security | 10% |
| Config & reproducibility | 10% |
| Operability & scale | 5% |
| Docs & maintainability | 5% |
| Observability | 5% |

Show the arithmetic. Give each score a reason in the findings' own terms.

## Write it

A new dated file beside the earlier `docs/audit-*.md`: verdict and score with the change since the last audit,
scorecard, what ran, what changed, findings by severity, what the checks caught and
missed, and four fixes in order. If the user wants the page too, keep its existing
design and update the same link; an artifact belongs to one account, so if the link
cannot be written, say so rather than quietly creating another.

## Honesty rules

- **If you wrote code you are scoring, say so on the page** and call the score provisional.
- Verify a draft against the evidence before publishing. Check counts, ranges and
  dates; the fifth audit's draft had several wrong ones.
- A finding without evidence is a suspicion, and should read as one.
- State what the audit did not cover.
