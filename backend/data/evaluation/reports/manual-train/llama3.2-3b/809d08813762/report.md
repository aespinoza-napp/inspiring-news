# manual-train · llama3.2:3b · the annotator's evidence (oracle)

Run `809d08813762` · provider `host.docker.internal:11434` · harness v1 · thresholds `95cb7cf5a88b` · corpus `snapshot` (12 points)

Dataset sha256 `b261d136c662`, 69 rows; 69 run, 0 not run. Commits: `4e0e67ff3f1e`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 69 | 66 |
| Accuracy | 55.1% [43.5%, 66.7%] | 54.5% [42.4%, 66.7%] |
| Macro-F1 (gold classes) | 0.375 [0.243, 0.477] | 0.368 [0.234, 0.473] |
| Coverage (not UNVERIFIED) | 91.3% [84.1%, 97.1%] | 90.9% [83.3%, 97.0%] |
| Selective accuracy | 55.6% [43.5%, 67.7%] | 55.0% [42.4%, 67.8%] |
| Cohen's kappa vs gold | 0.190 [-0.003, 0.379] | 0.177 [-0.023, 0.371] |

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
| temporalLeak (cited source newer than the claim) | 3 | 63 | 3 | fact088, fact146, fact176 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 69 |  |

Ranked but uncited sources newer than the claim: 0 over 0 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 76.3% | 64.4% | 0.699 | 45 | 38 |
| PARTIALLY_TRUE | n/a | 0.0% | 0.000 | 3 | 0 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 24.0% | 40.0% | 0.300 | 15 | 25 |
| UNVERIFIED | 50.0% | 50.0% | 0.500 | 6 | 6 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 29 | 0 | 0 | 14 | 2 |
| PARTIALLY_TRUE | 1 | 0 | 0 | 2 | 0 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 8 | 0 | 0 | 6 | 1 |
| UNVERIFIED | 0 | 0 | 0 | 3 | 3 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 48 | 58.3% [43.8%, 72.9%] | 0.415 | 87.5% | 59.5% |
| es | 21 | 47.6% [28.6%, 66.7%] | 0.215 | 100.0% | 47.6% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| culture | 10 | 60.0% [30.0%, 90.0%] | 0.375 | 100.0% | 60.0% |
| environment | 16 | 68.8% [43.8%, 87.5%] | 0.519 | 87.5% | 64.3% |
| health | 15 | 60.0% [33.3%, 86.7%] | 0.426 | 80.0% | 75.0% |
| science | 17 | 41.2% [17.6%, 64.7%] | 0.439 | 94.1% | 37.5% |
| society | 11 | 45.5% [18.2%, 72.7%] | 0.238 | 100.0% | 45.5% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 37 | 59.5% [43.2%, 75.7%] | 0.316 | 100.0% | 59.5% |
| interpretive | 3 | 100.0% [100.0%, 100.0%] | 1.000 | 100.0% | 100.0% |
| numerical | 29 | 44.8% [27.6%, 62.1%] | 0.352 | 79.3% | 43.5% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| press_release | 1 | 100.0% [100.0%, 100.0%] | 1.000 | 100.0% | 100.0% |
| primary | 43 | 46.5% [32.6%, 60.5%] | 0.240 | 93.0% | 50.0% |
| reference_media | 25 | 68.0% [48.0%, 84.0%] | 0.497 | 88.0% | 63.6% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| mutated | 15 | 40.0% [13.3%, 66.7%] | 0.571 | 93.3% | 42.9% |
| natural | 54 | 59.3% [46.3%, 72.2%] | 0.440 | 90.7% | 59.2% |

## Evidence

No search: each claim was judged on the pages at its own reference links (FactChecker.check_against), every readable one kept, no pertinence gate. A claim with no link, or none readable, reached the model with no evidence and is UNVERIFIED.

## Response time

Seconds per stage over the 69 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 69 | 0.1 | 0.2 | 0.4 | 0.3% |
| Evidence retrieval | 0 | n/a | n/a | n/a | 0.0% |
| Ranking | 0 | n/a | n/a | n/a | 0.0% |
| The model's verdict (with its wait for a permit) | 63 | 40.3 | 54.1 | 72.1 | 89.5% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 69 | 41.3 | 60.8 | 76.5 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 63 (0) |
| Claims the model was not asked about | 6 |
| Prompt / completion tokens | 78460 / 10179 |
| Tokens per claim asked (prompt / completion) | 1245.4 / 161.6 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 21.663 / 32.244 / 45.018 |
| Claim latency, median / p90 (s) | 41.337 / 60.770 |
| Completion tokens per second | 7.0 |
| Cost | n/a (no price given, or tokens unknown) |

## Paired comparison

Baseline A: `llama3.2:3b` (`ba36c5721e58`, host.docker.internal:11434); candidate B: this run. Paired over the 69 claims both scored; 0 set apart on either side, 0 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 44.9% | 55.1% | +10.1 pts | [-2.9 pts, +24.6 pts] |
| macroF1 | 0.233 | 0.375 | +0.142 | [+0.002, +0.257] |
| coverage | 97.1% | 91.3% | -5.8 pts | [-13.0 pts, +1.4 pts] |
| selectiveAccuracy | 46.3% | 55.6% | +9.3 pts | [-4.4 pts, +23.4 pts] |
| kappa | 0.056 | 0.190 | +0.134 | [-0.107, +0.372] |

Only A right: 9; only B right: 16. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 69 claims both searched (0 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 67 | 11.9% | 94.0% | +82.1 pts [+73.1 pts, +91.0 pts] | 0 / 55 |
| Reference link among ranked evidence | 67 | 9.0% | 94.0% | +85.1 pts [+76.1 pts, +94.0 pts] | 0 / 57 |
| Reference link among cited evidence | 67 | 7.5% | 94.0% | +86.6 pts [+77.6 pts, +94.0 pts] | 0 / 58 |
| Reference domain among candidates | 67 | 32.8% | 94.0% | +61.2 pts [+49.2 pts, +73.1 pts] | 0 / 41 |
| Reference domain among ranked evidence | 67 | 25.4% | 94.0% | +68.7 pts [+56.7 pts, +79.1 pts] | 0 / 46 |
| Reference domain among cited evidence | 67 | 19.4% | 94.0% | +74.6 pts [+64.2 pts, +85.1 pts] | 0 / 50 |
| Link MRR (ranked) | 67 | 7.0% | 94.0% | +87.0 pts [+78.5 pts, +94.5 pts] | 0 / 59 |
| Domain MRR (ranked) | 67 | 16.1% | 94.0% | +77.9 pts [+68.6 pts, +86.4 pts] | 0 / 56 |
| Claims with any ranked evidence | 69 | 98.6% | 91.3% | -7.2 pts [-14.5 pts, +0.0 pts] |  |
| Candidates per claim | 69 | 18.49 | 1.70 | -16.80 [-17.71, -15.88] |  |
| Ranked sources per claim | 69 | 4.74 | 1.70 | -3.04 [-3.32, -2.74] |  |
| Share cut at ranking (gate, cap) | 63 | 5.3% | 0.0% | -5.3 pts [-9.6 pts, -2.1 pts] |  |
| Distinct domains among ranked | 69 | 4.74 | 1.62 | -3.12 [-3.39, -2.81] |  |
| Ranked from rated domains | 62 | 7.7% | 8.1% | +0.3 pts [-4.8 pts, +6.5 pts] |  |
| Ranked from the internal corpus | 62 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
