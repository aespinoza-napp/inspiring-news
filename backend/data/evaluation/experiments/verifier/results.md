# The verifier's FALSE: results

2026-10-22, by the rule in `rule.md`. Detail and discussion:
`docs/decisions/evaluation.md`, "The verifier's FALSE". Reports under
`data/evaluation/reports/manual-{train,test}/llama3.2-3b/<run>/`.

## Train half (69 claims), replays of `2a4d7dde37b2`

| Entry | Run | Accuracy | vs B0 [95% CI] | Confidently wrong | FALSE to true claims | Decision |
|---|---|---|---|---|---|---|
| B0, thorough, list verifier (searched) | `2a4d7dde37b2` | 44.9% | | 36 | 24 of 45 | baseline |
| R0, B0 replayed (10 claims) | `9adb65e5ab94` | | 10 of 10 identical | | | the model's own noise: none |
| V1, stated rules | `20c970d87114` | 36.2% | -8.7 [-17.4, 0.0] | 30 | 19 | not adopted |
| V2, one source at a time, first rule | `d70e76cc6319` | 39.1% | -5.8 [-20.3, +8.7] | 32 | 6 | not adopted |
| V2b, one source at a time, by majority | `a2b3a553f3c0` | 47.8% | +2.9 [-11.6, +17.4] | 18 | 6 | to the test half |
| V3, `qwen3.5:9b`, list verifier | running | | | | | |

## Test half (70 claims), replays of `66034c5fea72`

| Entry | Run | Accuracy | vs B0 [95% CI] | Selective | Confidently wrong | Natural / altered claims | Decision |
|---|---|---|---|---|---|---|---|
| B0, thorough, list verifier (searched) | `66034c5fea72` | 51.4% | | 52.2% | 33 | 49.1% / 60.0% | baseline |
| V2b | `e7231c962477` | 55.7% | +4.3 [-8.6, +17.1] | 66.1% (+13.9 [+0.3, +27.3]) | 20 | 67.3% / 13.3% | **adopted** |

V2b is `VERIFIER_ANSWER=per_source`, the default since. It rarely catches
a claim with one altered detail: that is the next thing to fix.
