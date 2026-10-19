# manual-train · qwen3.5:9b · the annotator's evidence (oracle)

Run `8ef44d0de909` · provider `host.docker.internal:11434` · harness v1 · thresholds `95cb7cf5a88b` · corpus `snapshot` (12 points)

Dataset sha256 `b261d136c662`, 69 rows; 69 run, 0 not run. Commits: `4e0e67ff3f1e`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 69 | 66 |
| Accuracy | 56.5% [44.9%, 68.1%] | 54.5% [42.4%, 66.7%] |
| Macro-F1 (gold classes) | 0.386 [0.289, 0.473] | 0.374 [0.275, 0.466] |
| Coverage (not UNVERIFIED) | 69.6% [58.0%, 79.7%] | 68.2% [57.6%, 78.8%] |
| Selective accuracy | 72.9% [60.0%, 84.8%] | 71.1% [57.1%, 84.0%] |
| Cohen's kappa vs gold | 0.307 [0.146, 0.464] | 0.282 [0.121, 0.449] |

## What was set apart

Never in the error rate: each would measure an outage, not the pipeline.

| Outcome | Claims | Ids |
|---|---|---|
| error | 0 |  |
| searchUnavailable | 0 |  |
| llmUnreachable | 0 |  |
| scored | 69 |  |

| Flag | Flagged | Clear | Undetermined / n.a. | Ids |
|---|---|---|---|---|
| temporalLeak (cited source newer than the claim) | 3 | 66 | 0 | fact088, fact146, fact176 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 69 |  |

Ranked but uncited sources newer than the claim: 0 over 0 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 83.9% | 57.8% | 0.684 | 45 | 31 |
| PARTIALLY_TRUE | n/a | 0.0% | 0.000 | 3 | 0 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 52.9% | 60.0% | 0.562 | 15 | 17 |
| UNVERIFIED | 19.0% | 66.7% | 0.296 | 6 | 21 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 26 | 0 | 0 | 6 | 13 |
| PARTIALLY_TRUE | 2 | 0 | 0 | 1 | 0 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 2 | 0 | 0 | 9 | 4 |
| UNVERIFIED | 1 | 0 | 0 | 1 | 4 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 48 | 58.3% [43.8%, 72.9%] | 0.391 | 68.8% | 75.8% |
| es | 21 | 52.4% [28.6%, 71.4%] | 0.372 | 71.4% | 66.7% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| culture | 10 | 70.0% [40.0%, 100.0%] | 0.792 | 80.0% | 87.5% |
| environment | 16 | 50.0% [25.0%, 75.0%] | 0.395 | 75.0% | 50.0% |
| health | 15 | 53.3% [26.7%, 80.0%] | 0.412 | 60.0% | 88.9% |
| science | 17 | 58.8% [35.3%, 82.4%] | 0.357 | 70.6% | 75.0% |
| society | 11 | 54.5% [27.3%, 81.8%] | 0.500 | 63.6% | 71.4% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 37 | 73.0% [56.8%, 86.5%] | 0.525 | 83.8% | 87.1% |
| interpretive | 3 | 33.3% [0.0%, 100.0%] | 0.500 | 33.3% | 100.0% |
| numerical | 29 | 37.9% [20.7%, 55.2%] | 0.294 | 55.2% | 43.8% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| press_release | 1 | 100.0% [100.0%, 100.0%] | 1.000 | 100.0% | 100.0% |
| primary | 43 | 44.2% [30.2%, 58.1%] | 0.292 | 60.5% | 69.2% |
| reference_media | 25 | 76.0% [60.0%, 92.0%] | 0.585 | 84.0% | 76.2% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| mutated | 15 | 60.0% [33.3%, 86.7%] | 0.750 | 73.3% | 81.8% |
| natural | 54 | 55.6% [42.6%, 68.5%] | 0.350 | 68.5% | 70.3% |

## Evidence

No search: each claim was judged on the pages at its own reference links (FactChecker.check_against), every readable one kept, no pertinence gate. A claim with no link, or none readable, reached the model with no evidence and is UNVERIFIED.

## Response time

Seconds per stage over the 69 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 69 | 0.1 | 0.1 | 0.3 | 0.1% |
| Evidence retrieval | 0 | n/a | n/a | n/a | 0.0% |
| Ranking | 0 | n/a | n/a | n/a | 0.0% |
| The model's verdict (with its wait for a permit) | 63 | 123.7 | 153.6 | 187.2 | 96.1% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 69 | 125.0 | 159.2 | 190.7 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 63 (0) |
| Claims the model was not asked about | 6 |
| Prompt / completion tokens | 79246 / 13242 |
| Tokens per claim asked (prompt / completion) | 1257.9 / 210.2 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 61.381 / 85.569 / 124.108 |
| Claim latency, median / p90 (s) | 125.007 / 159.176 |
| Completion tokens per second | 3.3 |
| Cost | n/a (no price given, or tokens unknown) |

## Paired comparison

Baseline A: `llama3.2:3b` (`809d08813762`, host.docker.internal:11434); candidate B: this run. Paired over the 69 claims both scored; 0 set apart on either side, 0 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 55.1% | 56.5% | +1.4 pts | [-11.6 pts, +14.5 pts] |
| macroF1 | 0.375 | 0.386 | +0.011 | [-0.095, +0.126] |
| coverage | 91.3% | 69.6% | -21.7 pts | [-31.9 pts, -13.0 pts] |
| selectiveAccuracy | 55.6% | 72.9% | +17.4 pts | [+2.7 pts, +32.0 pts] |
| kappa | 0.190 | 0.307 | +0.117 | [-0.086, +0.326] |

Only A right: 11; only B right: 12. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 69 claims both searched (0 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 67 | 94.0% | 94.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among ranked evidence | 67 | 94.0% | 94.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among cited evidence | 67 | 94.0% | 80.6% | -13.4 pts [-22.4 pts, -6.0 pts] | 9 / 0 |
| Reference domain among candidates | 67 | 94.0% | 94.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among ranked evidence | 67 | 94.0% | 94.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among cited evidence | 67 | 94.0% | 80.6% | -13.4 pts [-22.4 pts, -6.0 pts] | 9 / 0 |
| Link MRR (ranked) | 67 | 94.0% | 94.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Domain MRR (ranked) | 67 | 94.0% | 94.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Claims with any ranked evidence | 69 | 91.3% | 91.3% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Candidates per claim | 69 | 1.70 | 1.70 | +0.00 [+0.00, +0.00] |  |
| Ranked sources per claim | 69 | 1.70 | 1.70 | +0.00 [+0.00, +0.00] |  |
| Share cut at ranking (gate, cap) | 63 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Distinct domains among ranked | 69 | 1.62 | 1.62 | +0.00 [+0.00, +0.00] |  |
| Ranked from rated domains | 63 | 7.9% | 7.9% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Ranked from the internal corpus | 63 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
