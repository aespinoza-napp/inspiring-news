# manual-train · qwen3.5:4b

Run `5a4f4ee5baac` · provider `host.docker.internal:11434` · harness v1 · thresholds `95cb7cf5a88b` · corpus `snapshot` (12 points)

Dataset sha256 `b261d136c662`, 69 rows; 69 run, 0 not run. Commits: `4e0e67ff3f1e`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 69 | 42 |
| Accuracy | 30.4% [20.3%, 42.0%] | 28.6% [16.7%, 42.9%] |
| Macro-F1 (gold classes) | 0.236 [0.149, 0.320] | 0.219 [0.117, 0.319] |
| Coverage (not UNVERIFIED) | 72.5% [60.9%, 82.6%] | 71.4% [57.1%, 83.3%] |
| Selective accuracy | 38.0% [24.5%, 51.1%] | 36.7% [20.0%, 54.2%] |
| Cohen's kappa vs gold | 0.091 [-0.011, 0.200] | 0.081 [-0.047, 0.219] |

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
| temporalLeak (cited source newer than the claim) | 27 | 18 | 24 | fact020, fact021, fact036, fact049, fact062, fact065, fact085, fact088, fact089, fact099, fact101, fact106, fact116, fact118, fact122, fact124, fact128, fact129, fact133, fact138, fact142, fact143, fact144, fact145, fact146, fact156, fact162 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 69 |  |

Ranked but uncited sources newer than the claim: 4 over 4 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 85.7% | 26.7% | 0.407 | 45 | 14 |
| PARTIALLY_TRUE | 0.0% | 0.0% | 0.000 | 3 | 14 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 31.8% | 46.7% | 0.378 | 15 | 22 |
| UNVERIFIED | 10.5% | 33.3% | 0.160 | 6 | 19 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 12 | 11 | 0 | 11 | 11 |
| PARTIALLY_TRUE | 1 | 0 | 0 | 1 | 1 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 0 | 3 | 0 | 7 | 5 |
| UNVERIFIED | 1 | 0 | 0 | 3 | 2 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 48 | 25.0% [12.5%, 37.5%] | 0.194 | 68.8% | 33.3% |
| es | 21 | 42.9% [23.8%, 66.7%] | 0.340 | 81.0% | 47.1% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| culture | 10 | 40.0% [10.0%, 70.0%] | 0.554 | 90.0% | 44.4% |
| environment | 16 | 18.8% [0.0%, 37.5%] | 0.127 | 75.0% | 25.0% |
| health | 15 | 26.7% [6.7%, 46.7%] | 0.178 | 60.0% | 44.4% |
| science | 17 | 35.3% [11.8%, 58.8%] | 0.259 | 58.8% | 50.0% |
| society | 11 | 36.4% [9.1%, 63.6%] | 0.484 | 90.9% | 30.0% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 37 | 35.1% [18.9%, 51.4%] | 0.333 | 81.1% | 43.3% |
| interpretive | 3 | 33.3% [0.0%, 100.0%] | 0.500 | 66.7% | 50.0% |
| numerical | 29 | 24.1% [10.3%, 41.4%] | 0.190 | 62.1% | 27.8% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| press_release | 1 | 0.0% [0.0%, 0.0%] | 0.000 | 100.0% | 0.0% |
| primary | 43 | 27.9% [14.0%, 41.9%] | 0.203 | 62.8% | 40.7% |
| reference_media | 25 | 36.0% [16.0%, 56.0%] | 0.308 | 88.0% | 36.4% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| mutated | 15 | 46.7% [20.0%, 73.3%] | 0.636 | 66.7% | 70.0% |
| natural | 54 | 25.9% [14.8%, 38.9%] | 0.202 | 74.1% | 30.0% |

## Retrieval

69 claims searched (67 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 0 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 13.4% [6.0%, 22.4%] (n=67) |
| Reference link among ranked evidence | 10.4% [4.5%, 17.9%] (n=67) |
| Reference link among cited evidence | 10.4% [4.5%, 17.9%] (n=67) |
| Reference domain among candidates | 35.8% [23.9%, 47.8%] (n=67) |
| Reference domain among ranked evidence | 28.4% [17.9%, 38.8%] (n=67) |
| Reference domain among cited evidence | 25.4% [14.9%, 35.8%] (n=67) |
| Link MRR (ranked) | 7.4% [2.2%, 13.7%] (n=67) |
| Domain MRR (ranked) | 18.0% [10.4%, 26.2%] (n=67) |
| Claims with any ranked evidence | 100.0% [100.0%, 100.0%] (n=69) |
| Candidates per claim | 18.26 [17.32, 19.22] (n=69) |
| Ranked sources per claim | 4.75 [4.57, 4.91] (n=69) |
| Share cut at ranking (gate, cap) | 4.5% [1.7%, 8.0%] (n=69) |
| Distinct domains among ranked | 4.75 [4.57, 4.91] (n=69) |
| Ranked from rated domains | 6.7% [4.1%, 9.6%] (n=69) |
| Ranked from the internal corpus | 0.0% [0.0%, 0.0%] (n=69) |
| Fact-checker's own page ranked (x-fact) | n/a (n=0) |
| Retrieval seconds per claim | 11.44 [10.64, 12.36] (n=69) |
| Ranking seconds per claim | 5.18 [4.86, 5.50] (n=69) |

Medians: 17.00 candidates, 5.00 ranked, 10.49 s retrieval, 4.96 s ranking; 3.00 queries per claim.

Ranked sources found by: proposition 202, anchor 134, refutation 82 (a source two queries found counts for both).

References found, then cut:

- evidence_retrieval: same domain as a higher-ranked source (pewresearch.org): 2

| By dataset | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| custom | 69 | 67 | 10.4% | 28.4% | 100.0% |

| By language | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| en | 48 | 46 | 10.9% | 23.9% | 100.0% |
| es | 21 | 21 | 9.5% | 38.1% | 100.0% |

## Response time

Seconds per stage over the 69 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 69 | 0.1 | 0.1 | 1.6 | 0.1% |
| Evidence retrieval | 69 | 10.5 | 15.4 | 29.1 | 10.5% |
| Ranking | 69 | 5.0 | 7.2 | 8.2 | 4.7% |
| The model's verdict (with its wait for a permit) | 69 | 93.2 | 113.5 | 128.7 | 84.7% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 69 | 109.9 | 130.5 | 144.4 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 69 (0) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 132567 / 15644 |
| Tokens per claim asked (prompt / completion) | 1921.3 / 226.7 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 53.580 / 68.590 / 75.436 |
| Claim latency, median / p90 (s) | 109.945 / 130.534 |
| Completion tokens per second | 4.1 |
| Cost | n/a (no price given, or tokens unknown) |

## Paired comparison

Baseline A: `llama3.2:3b` (`ba36c5721e58`, host.docker.internal:11434); candidate B: this run. Paired over the 69 claims both scored; 0 set apart on either side, 0 only in A, 0 only in B.

| Statistic | A | B | B − A | 95% CI of B − A |
|---|---|---|---|---|
| accuracy | 44.9% | 30.4% | -14.5 pts | [-29.0 pts, +0.0 pts] |
| macroF1 | 0.233 | 0.236 | +0.004 | [-0.099, +0.106] |
| coverage | 97.1% | 72.5% | -24.6 pts | [-36.2 pts, -13.0 pts] |
| selectiveAccuracy | 46.3% | 38.0% | -8.3 pts | [-24.3 pts, +7.6 pts] |
| kappa | 0.056 | 0.091 | +0.035 | [-0.157, +0.234] |

Only A right: 19; only B right: 9. An interval that excludes 0 is a difference the resampling cannot explain away.

### Retrieval: B − A

Paired over 69 claims both searched (0 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 67 | 11.9% | 13.4% | +1.5 pts [-3.0 pts, +7.5 pts] | 1 / 2 |
| Reference link among ranked evidence | 67 | 9.0% | 10.4% | +1.5 pts [-3.0 pts, +7.5 pts] | 1 / 2 |
| Reference link among cited evidence | 67 | 7.5% | 10.4% | +3.0 pts [-3.0 pts, +9.0 pts] | 1 / 3 |
| Reference domain among candidates | 67 | 32.8% | 35.8% | +3.0 pts [-3.0 pts, +9.0 pts] | 1 / 3 |
| Reference domain among ranked evidence | 67 | 25.4% | 28.4% | +3.0 pts [-4.5 pts, +10.4 pts] | 2 / 4 |
| Reference domain among cited evidence | 67 | 19.4% | 25.4% | +6.0 pts [-3.0 pts, +14.9 pts] | 3 / 7 |
| Link MRR (ranked) | 67 | 7.0% | 7.4% | +0.4 pts [-4.2 pts, +4.8 pts] | 1 / 3 |
| Domain MRR (ranked) | 67 | 16.1% | 18.0% | +1.9 pts [-4.5 pts, +8.3 pts] | 2 / 7 |
| Claims with any ranked evidence | 69 | 98.6% | 100.0% | +1.5 pts [+0.0 pts, +4.3 pts] |  |
| Candidates per claim | 69 | 18.49 | 18.26 | -0.23 [-0.93, +0.45] |  |
| Ranked sources per claim | 69 | 4.74 | 4.75 | +0.01 [-0.16, +0.22] |  |
| Share cut at ranking (gate, cap) | 69 | 4.8% | 4.5% | -0.3 pts [-4.3 pts, +3.2 pts] |  |
| Distinct domains among ranked | 69 | 4.74 | 4.75 | +0.01 [-0.16, +0.22] |  |
| Ranked from rated domains | 68 | 7.1% | 6.8% | -0.3 pts [-1.5 pts, +0.9 pts] |  |
| Ranked from the internal corpus | 68 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Retrieval seconds per claim | 69 | 14.35 | 11.44 | -2.91 [-4.52, -1.35] |  |
| Ranking seconds per claim | 69 | 6.40 | 5.18 | -1.22 [-2.07, -0.49] |  |
