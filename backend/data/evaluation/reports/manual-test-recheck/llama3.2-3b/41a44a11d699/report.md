# manual-test-recheck · llama3.2:3b

Run `41a44a11d699` · provider `host.docker.internal:11434` · harness v1 · thresholds `e1bae39fd2a3` · corpus `snapshot` (12 points)

Dataset sha256 `f3e53acb0345`, 14 rows; 14 run, 0 not run. Commits: `4e0e67ff3f1e`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 14 | 8 |
| Accuracy | 57.1% [28.6%, 85.7%] | 62.5% [25.0%, 87.5%] |
| Macro-F1 (gold classes) | 0.321 [0.168, 0.435] | 0.440 [0.182, 0.636] |
| Coverage (not UNVERIFIED) | 100.0% [100.0%, 100.0%] | 100.0% [100.0%, 100.0%] |
| Selective accuracy | 57.1% [28.6%, 85.7%] | 62.5% [25.0%, 87.5%] |
| Cohen's kappa vs gold | 0.328 [0.048, 0.647] | 0.385 [0.000, 0.778] |

## What was set apart

Never in the error rate: each would measure an outage, not the pipeline.

| Outcome | Claims | Ids |
|---|---|---|
| error | 0 |  |
| searchUnavailable | 0 |  |
| llmUnreachable | 0 |  |
| scored | 14 |  |

| Flag | Flagged | Clear | Undetermined / n.a. | Ids |
|---|---|---|---|---|
| temporalLeak (cited source newer than the claim) | 6 | 3 | 5 | fact031, fact053, fact057, fact084, fact149, fact150 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 14 |  |

Ranked but uncited sources newer than the claim: 0 over 0 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 80.0% | 57.1% | 0.667 | 7 | 5 |
| PARTIALLY_TRUE | n/a | 0.0% | 0.000 | 1 | 0 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 44.4% | 100.0% | 0.615 | 4 | 9 |
| UNVERIFIED | n/a | 0.0% | 0.000 | 2 | 0 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 4 | 0 | 0 | 3 | 0 |
| PARTIALLY_TRUE | 0 | 0 | 0 | 1 | 0 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 0 | 0 | 0 | 4 | 0 |
| UNVERIFIED | 1 | 0 | 0 | 1 | 0 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 12 | 58.3% [33.3%, 83.3%] | 0.422 | 100.0% | 58.3% |
| es | 2 | 50.0% [0.0%, 100.0%] | 0.500 | 100.0% | 50.0% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| culture | 3 | 66.7% [0.0%, 100.0%] | 0.800 | 100.0% | 66.7% |
| environment | 3 | 66.7% [0.0%, 100.0%] | 0.556 | 100.0% | 66.7% |
| health | 2 | 50.0% [0.0%, 100.0%] | 0.500 | 100.0% | 50.0% |
| science | 3 | 33.3% [0.0%, 100.0%] | 0.250 | 100.0% | 33.3% |
| society | 3 | 66.7% [0.0%, 100.0%] | 0.500 | 100.0% | 66.7% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 9 | 66.7% [33.3%, 100.0%] | 0.375 | 100.0% | 66.7% |
| numerical | 5 | 40.0% [0.0%, 80.0%] | 0.300 | 100.0% | 40.0% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| press_release | 2 | 50.0% [0.0%, 100.0%] | 0.500 | 100.0% | 50.0% |
| primary | 8 | 50.0% [12.5%, 87.5%] | 0.292 | 100.0% | 50.0% |
| reference_media | 4 | 75.0% [25.0%, 100.0%] | 0.733 | 100.0% | 75.0% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| mutated | 4 | 100.0% [100.0%, 100.0%] | 1.000 | 100.0% | 100.0% |
| natural | 10 | 40.0% [10.0%, 70.0%] | 0.222 | 100.0% | 40.0% |

## Retrieval

14 claims searched (14 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 0 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 14.3% [0.0%, 35.7%] (n=14) |
| Reference link among ranked evidence | 7.1% [0.0%, 21.4%] (n=14) |
| Reference link among cited evidence | 7.1% [0.0%, 21.4%] (n=14) |
| Reference domain among candidates | 42.9% [21.4%, 71.4%] (n=14) |
| Reference domain among ranked evidence | 28.6% [7.1%, 50.0%] (n=14) |
| Reference domain among cited evidence | 7.1% [0.0%, 21.4%] (n=14) |
| Link MRR (ranked) | 1.4% [0.0%, 4.3%] (n=14) |
| Domain MRR (ranked) | 7.0% [1.4%, 13.3%] (n=14) |
| Claims with any ranked evidence | 100.0% [100.0%, 100.0%] (n=14) |
| Candidates per claim | 20.07 [17.71, 22.43] (n=14) |
| Ranked sources per claim | 5.00 [5.00, 5.00] (n=14) |
| Share cut at ranking (gate, cap) | 11.9% [2.7%, 22.6%] (n=14) |
| Distinct domains among ranked | 5.00 [5.00, 5.00] (n=14) |
| Ranked from rated domains | 5.7% [1.4%, 11.4%] (n=14) |
| Ranked from the internal corpus | 0.0% [0.0%, 0.0%] (n=14) |
| Fact-checker's own page ranked (x-fact) | n/a (n=0) |
| Retrieval seconds per claim | 13.96 [10.67, 17.78] (n=14) |
| Ranking seconds per claim | 7.17 [5.31, 9.52] (n=14) |

Medians: 21.00 candidates, 5.00 ranked, 10.83 s retrieval, 6.06 s ranking; 3.00 queries per claim.

Ranked sources found by: proposition 40, anchor 23, refutation 14, follow_up 6 (a source two queries found counts for both).

References found, then cut:

- evidence_retrieval: cut by pre-rank funnel (rank 6 of 11, top 5 kept): 1
- evidence_retrieval: same domain as a higher-ranked source (space.com): 1

| By dataset | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| custom | 14 | 14 | 7.1% | 28.6% | 100.0% |

| By language | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| en | 12 | 12 | 8.3% | 33.3% | 100.0% |
| es | 2 | 2 | 0.0% | 0.0% | 100.0% |

## Response time

Seconds per stage over the 14 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 14 | 0.1 | 0.3 | 0.4 | 0.1% |
| Evidence retrieval | 14 | 10.8 | 24.7 | 29.3 | 6.8% |
| Ranking | 14 | 6.1 | 12.0 | 18.8 | 3.5% |
| The model's verdict (with its wait for a permit) | 14 | 131.4 | 215.7 | 236.0 | 67.8% |
| Second look, where taken | 4 | 167.3 | 176.4 | 179.7 | 21.9% |
| Whole claim | 14 | 150.6 | 387.4 | 430.2 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 22 (0) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 37347 / 3556 |
| Tokens per claim asked (prompt / completion) | 2667.6 / 254.0 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 62.849 / 85.170 / 131.645 |
| Claim latency, median / p90 (s) | 150.621 / 387.367 |
| Completion tokens per second | 2.4 |
| Cost | n/a (no price given, or tokens unknown) |
