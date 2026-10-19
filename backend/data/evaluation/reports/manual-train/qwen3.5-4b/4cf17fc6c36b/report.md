# manual-train · qwen3.5:4b · the annotator's evidence (oracle)

Run `4cf17fc6c36b` · provider `host.docker.internal:11434` · harness v1 · thresholds `95cb7cf5a88b` · corpus `snapshot` (12 points)

Dataset sha256 `b261d136c662`, 69 rows; 69 run, 0 not run. Commits: `4e0e67ff3f1e`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 69 | 66 |
| Accuracy | 34.8% [23.2%, 46.4%] | 33.3% [22.7%, 45.5%] |
| Macro-F1 (gold classes) | 0.316 [0.211, 0.417] | 0.306 [0.196, 0.412] |
| Coverage (not UNVERIFIED) | 76.8% [66.7%, 87.0%] | 75.8% [65.2%, 84.8%] |
| Selective accuracy | 39.6% [26.4%, 52.8%] | 38.0% [24.5%, 51.9%] |
| Cohen's kappa vs gold | 0.168 [0.053, 0.286] | 0.154 [0.039, 0.275] |

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
| TRUE | 84.6% | 24.4% | 0.379 | 45 | 13 |
| PARTIALLY_TRUE | 4.8% | 33.3% | 0.083 | 3 | 21 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 47.4% | 60.0% | 0.529 | 15 | 19 |
| UNVERIFIED | 18.8% | 50.0% | 0.273 | 6 | 16 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 11 | 14 | 0 | 9 | 11 |
| PARTIALLY_TRUE | 2 | 1 | 0 | 0 | 0 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 0 | 4 | 0 | 9 | 2 |
| UNVERIFIED | 0 | 2 | 0 | 1 | 3 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 48 | 35.4% [22.9%, 50.0%] | 0.330 | 79.2% | 36.8% |
| es | 21 | 33.3% [14.3%, 52.4%] | 0.310 | 71.4% | 46.7% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| culture | 10 | 40.0% [10.0%, 70.0%] | 0.500 | 90.0% | 44.4% |
| environment | 16 | 50.0% [25.0%, 75.0%] | 0.425 | 75.0% | 50.0% |
| health | 15 | 20.0% [0.0%, 40.0%] | 0.229 | 60.0% | 33.3% |
| science | 17 | 41.2% [17.6%, 64.7%] | 0.380 | 70.6% | 50.0% |
| society | 11 | 18.2% [0.0%, 45.5%] | 0.229 | 100.0% | 18.2% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 37 | 37.8% [21.6%, 54.1%] | 0.345 | 89.2% | 42.4% |
| interpretive | 3 | 33.3% [0.0%, 100.0%] | 0.500 | 66.7% | 50.0% |
| numerical | 29 | 31.0% [13.8%, 48.3%] | 0.301 | 62.1% | 33.3% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| press_release | 1 | 0.0% [0.0%, 0.0%] | 0.000 | 100.0% | 0.0% |
| primary | 43 | 23.3% [11.6%, 37.2%] | 0.188 | 72.1% | 32.3% |
| reference_media | 25 | 56.0% [36.0%, 76.0%] | 0.567 | 84.0% | 52.4% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| mutated | 15 | 60.0% [33.3%, 80.0%] | 0.750 | 86.7% | 69.2% |
| natural | 54 | 27.8% [16.7%, 40.7%] | 0.260 | 74.1% | 30.0% |

## Evidence

No search: each claim was judged on the pages at its own reference links (FactChecker.check_against), every readable one kept, no pertinence gate. A claim with no link, or none readable, reached the model with no evidence and is UNVERIFIED.

## Response time

Seconds per stage over the 69 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 69 | 0.1 | 0.1 | 0.2 | 0.1% |
| Evidence retrieval | 0 | n/a | n/a | n/a | 0.0% |
| Ranking | 0 | n/a | n/a | n/a | 0.0% |
| The model's verdict (with its wait for a permit) | 0 | n/a | n/a | n/a | 0.0% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 69 | 58.5 | 78.4 | 89.5 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 63 (0) |
| Claims the model was not asked about | 6 |
| Prompt / completion tokens | 79246 / 10275 |
| Tokens per claim asked (prompt / completion) | 1257.9 / 163.1 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 30.589 / 41.647 / 48.774 |
| Claim latency, median / p90 (s) | 58.504 / 78.389 |
| Completion tokens per second | 5.3 |
| Cost | n/a (no price given, or tokens unknown) |

## Paired comparison

Baseline A: `llama3.2:3b` (`809d08813762`, host.docker.internal:11434); candidate B: this run. Paired over the 69 claims both scored; 0 set apart on either side, 0 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 55.1% | 34.8% | -20.3 pts | [-34.8 pts, -5.8 pts] |
| macroF1 | 0.375 | 0.316 | -0.059 | [-0.166, +0.052] |
| coverage | 91.3% | 76.8% | -14.5 pts | [-23.2 pts, -7.2 pts] |
| selectiveAccuracy | 55.6% | 39.6% | -15.9 pts | [-33.0 pts, +1.5 pts] |
| kappa | 0.190 | 0.168 | -0.022 | [-0.215, +0.181] |

Only A right: 22; only B right: 8. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 69 claims both searched (0 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 67 | 94.0% | 94.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among ranked evidence | 67 | 94.0% | 94.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference link among cited evidence | 67 | 94.0% | 94.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among candidates | 67 | 94.0% | 94.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among ranked evidence | 67 | 94.0% | 94.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among cited evidence | 67 | 94.0% | 94.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Link MRR (ranked) | 67 | 94.0% | 94.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Domain MRR (ranked) | 67 | 94.0% | 94.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Claims with any ranked evidence | 69 | 91.3% | 91.3% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Candidates per claim | 69 | 1.70 | 1.70 | +0.00 [+0.00, +0.00] |  |
| Ranked sources per claim | 69 | 1.70 | 1.70 | +0.00 [+0.00, +0.00] |  |
| Share cut at ranking (gate, cap) | 63 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Distinct domains among ranked | 69 | 1.62 | 1.62 | +0.00 [+0.00, +0.00] |  |
| Ranked from rated domains | 63 | 7.9% | 7.9% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Ranked from the internal corpus | 63 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
