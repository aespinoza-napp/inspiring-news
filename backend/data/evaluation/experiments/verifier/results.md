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
| V3, `qwen3.5:9b`, list verifier (2 timed out) | `594130bf966f` | 50.7% | +4.5 [-10.4, +19.4] | 15 | 8 | better than B0 by the rule; ~90 s a call: the case for a faster endpoint |
| V4, quote first (against V2b) | `7975364fe90b` | 47.8% | +0.0 [-13.0, +13.0] vs V2b | 25 | 11 | not adopted |
| V5, the 9B one source at a time | `854f7aa29f3a` | 52.2% | +7.2 [-5.8, +20.3] | 17 | 9 | meets the rule: to the test half |

## Test half (70 claims), replays of `66034c5fea72`

| Entry | Run | Accuracy | vs B0 [95% CI] | Selective | Confidently wrong | Natural / altered claims | Decision |
|---|---|---|---|---|---|---|---|
| B0, thorough, list verifier (searched) | `66034c5fea72` | 51.4% | | 52.2% | 33 | 49.1% / 60.0% | baseline |
| V2b | `e7231c962477` | 55.7% | +4.3 [-8.6, +17.1] | 66.1% (+13.9 [+0.3, +27.3]) | 20 | 67.3% / 13.3% | **adopted** |

V2b is `VERIFIER_ANSWER=per_source`, the default since. It rarely catches
a claim with one altered detail. V3, the 9B, does (11 of 15) while
rarely calling a true claim false (8 of 44): selective accuracy 67.4%
against 47.7% (+19.7 [+4.1, +35.6]), kappa 0.282 against 0.141 - at
~90 s a call on this CPU.
