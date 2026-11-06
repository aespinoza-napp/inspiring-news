---
name: fact-check-change
description: The rules for changing anything that affects verdicts in the fact-checking pipeline, including retrieval, ranking, the verifier, thresholds, search engines or the confidence scorer, and how to measure the effect without spoiling the thesis evaluation. Use before such a change, or when comparing two versions of the pipeline.
---

# Changing what produces a verdict

The verdicts are what the thesis measures, so a change is also a change to the experiment.

## Before writing it

1. **Write the adoption rule first**, as `data/evaluation/experiments/verifier/rule.md`
   does, so the result cannot choose its own criterion.
2. **Touch only the train half.** `split.json` is frozen; the test half decides once.
   Say so in what you report.
3. **Check whether a searched-run comparison is even possible.** Two searched runs differ
   by 6-9 points from the web alone. Compare on fixed evidence.

## Building it

- A per-run tunable lives in `src/config/thresholds.py`: a setting for its default, a
  `PipelineThresholds` field, an `ThresholdOverrides` field (root `CLAUDE.md`, invariants).
- A change that must leave old behaviour reachable gets a pin in
  `data/evaluation/thresholds/thorough.json`.
- Put post-retrieval logic in `FactChecker._judge`, so replay and the second look
  go through it. Logic inside the retriever is invisible to a replay.
- A changed response shape bumps `AnalysisCache.SCHEMA_VERSION`.
- Evidence order is what the model cites: keep input order (`bounded_map`).

## Measuring it

**Since 2026-11-05 the benchmark is AVeriTeC** (`data/evaluation/experiments/averitec/protocol.md`,
`docs/decisions/evaluation.md`, "AVeriTeC"): tune on `averitec_train.jsonl --split train`, read
dev once per protocol, and no figure counts unless its report's temporal audit says **Held**. The
commands below still show the custom set, which remains for Spanish and for constructive news.

Simulating on recorded stances is a quick screen, not a result: on 3 Nov it said 47.8%
where the real replay said 46.4%, because a removed source frees a slot for another.

```bash
./scripts/stack.sh eval
cd docker && docker compose -f docker-compose.yml -f docker-compose.eval.yml \
  --env-file ../backend/.env run --rm --no-deps -T backend \
  python -m src.evaluation.cli run --dataset data/evaluation/manual --split train \
  --model <the baseline run's model> --replay <baseline run dir> --label <name>
```

Only runs since 22 Oct keep `evidence.jsonl`. Report the paired difference with its
interval (`cli report --run <dir> --compare <baseline>`), natural and altered claims
apart, confidently wrong answers, and which claims changed and why.

## Saying what it means

- "No detectable difference" is a result. Adopt for validity if that is the reason, and
  say accuracy did not rise.
- 108 of 139 labels are unreviewed: no custom-set figure is final.
- Name anything that flatters the number. Altered claims were made by editing real
  sentences, so a detector of edited sentences looks better there than in the wild.
- Not adopting something is also worth recording, with its numbers.

## Recording it

Add a dated section to `docs/fact-checking-changes.md`, and update the decision record
and the "Known" lists in `CLAUDE.md` if a reader could now be misled. Then run the
`verify` skill.
