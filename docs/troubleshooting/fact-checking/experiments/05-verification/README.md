# Experiments on [05-verification](../../05-verification.md)

One file per batch, `<batch>.md`, created by `scripts/troubleshoot.sh agent --batch <batch> --stage 05`.

- **Measured** is written by `backend/src/evaluation/troubleshoot.py` from the batch's
  files (`backend/data/evaluation/experiments/troubleshooting/fact-checking/<batch>/05-verification/`)
  and rewritten on every run: never edit it by hand, and check any number in the
  sections below against it.
- **Findings** and **Proposed change** are the agent's, each citing claim ids and the
  field of `comparison-before.json` it read.
- **Result of the change** is the before/after the script measured, offline for 01-02;
  for 03-05 the change goes to the iteration loop (`/iterate-fact-check`), which
  decides it on verdicts.

What an experiment establishes, once reviewed, goes into [the part's file](../../05-verification.md),
dated.

| Batch | Claims | Change proposed | Measured result | Adopted |
|---|---|---|---|---|
| [claude-search](../../README.md) (4 Nov, by hand) | first 20 train | see the part's file | - | - |
