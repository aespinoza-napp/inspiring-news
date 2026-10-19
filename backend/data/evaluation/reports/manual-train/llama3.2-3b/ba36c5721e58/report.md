# manual-train · llama3.2:3b

Run `ba36c5721e58` · provider `host.docker.internal:11434` · harness v1 · thresholds `95cb7cf5a88b` · corpus `snapshot` (12 points)

Dataset sha256 `b261d136c662`, 69 rows; 69 run, 0 not run. Commits: `4e0e67ff3f1e`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 69 | 52 |
| Accuracy | 44.9% [33.3%, 56.5%] | 36.5% [23.1%, 50.0%] |
| Macro-F1 (gold classes) | 0.233 [0.170, 0.291] | 0.199 [0.128, 0.267] |
| Coverage (not UNVERIFIED) | 97.1% [92.8%, 100.0%] | 96.2% [90.4%, 100.0%] |
| Selective accuracy | 46.3% [34.3%, 58.2%] | 38.0% [25.0%, 51.9%] |
| Cohen's kappa vs gold | 0.056 [-0.111, 0.220] | -0.045 [-0.239, 0.150] |

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
| temporalLeak (cited source newer than the claim) | 17 | 28 | 24 | fact009, fact020, fact036, fact062, fact065, fact085, fact089, fact099, fact101, fact116, fact118, fact128, fact133, fact142, fact144, fact146, fact162 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 69 |  |

Ranked but uncited sources newer than the claim: 17 over 17 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 69.7% | 51.1% | 0.590 | 45 | 33 |
| PARTIALLY_TRUE | 0.0% | 0.0% | 0.000 | 3 | 2 |
| MISLEADING | n/a | n/a | n/a | 0 | 0 |
| FALSE | 25.0% | 53.3% | 0.340 | 15 | 32 |
| UNVERIFIED | 0.0% | 0.0% | 0.000 | 6 | 2 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 23 | 2 | 0 | 18 | 2 |
| PARTIALLY_TRUE | 2 | 0 | 0 | 1 | 0 |
| MISLEADING | 0 | 0 | 0 | 0 | 0 |
| FALSE | 7 | 0 | 0 | 8 | 0 |
| UNVERIFIED | 1 | 0 | 0 | 5 | 0 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 48 | 45.8% [31.2%, 60.4%] | 0.236 | 95.8% | 47.8% |
| es | 21 | 42.9% [23.8%, 61.9%] | 0.224 | 100.0% | 42.9% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| culture | 10 | 80.0% [50.0%, 100.0%] | 0.829 | 90.0% | 88.9% |
| environment | 16 | 43.8% [18.8%, 68.8%] | 0.238 | 100.0% | 43.8% |
| health | 15 | 40.0% [13.3%, 66.7%] | 0.242 | 100.0% | 40.0% |
| science | 17 | 52.9% [29.4%, 76.5%] | 0.282 | 100.0% | 52.9% |
| society | 11 | 9.1% [0.0%, 27.3%] | 0.067 | 90.9% | 10.0% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 37 | 51.4% [35.1%, 67.6%] | 0.313 | 97.3% | 52.8% |
| interpretive | 3 | 66.7% [0.0%, 100.0%] | 0.800 | 100.0% | 66.7% |
| numerical | 29 | 34.5% [17.2%, 51.7%] | 0.205 | 96.6% | 35.7% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| press_release | 1 | 100.0% [100.0%, 100.0%] | 1.000 | 100.0% | 100.0% |
| primary | 43 | 48.8% [34.9%, 62.8%] | 0.246 | 97.7% | 50.0% |
| reference_media | 25 | 36.0% [20.0%, 56.0%] | 0.199 | 96.0% | 37.5% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| mutated | 15 | 53.3% [26.7%, 80.0%] | 0.696 | 100.0% | 53.3% |
| natural | 54 | 42.6% [29.6%, 55.6%] | 0.216 | 96.3% | 44.2% |

## Retrieval

69 claims searched (67 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 0 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 11.9% [4.5%, 20.9%] (n=67) |
| Reference link among ranked evidence | 9.0% [3.0%, 16.4%] (n=67) |
| Reference link among cited evidence | 7.5% [1.5%, 14.9%] (n=67) |
| Reference domain among candidates | 32.8% [22.4%, 44.8%] (n=67) |
| Reference domain among ranked evidence | 25.4% [14.9%, 35.8%] (n=67) |
| Reference domain among cited evidence | 19.4% [10.4%, 29.8%] (n=67) |
| Link MRR (ranked) | 7.0% [1.8%, 13.4%] (n=67) |
| Domain MRR (ranked) | 16.1% [9.0%, 24.3%] (n=67) |
| Claims with any ranked evidence | 98.6% [95.7%, 100.0%] (n=69) |
| Candidates per claim | 18.49 [17.62, 19.38] (n=69) |
| Ranked sources per claim | 4.74 [4.52, 4.90] (n=69) |
| Share cut at ranking (gate, cap) | 4.8% [1.9%, 8.8%] (n=69) |
| Distinct domains among ranked | 4.74 [4.52, 4.90] (n=69) |
| Ranked from rated domains | 7.1% [4.4%, 10.3%] (n=68) |
| Ranked from the internal corpus | 0.0% [0.0%, 0.0%] (n=68) |
| Fact-checker's own page ranked (x-fact) | n/a (n=0) |
| Retrieval seconds per claim | 14.35 [12.92, 16.00] (n=69) |
| Ranking seconds per claim | 6.40 [5.62, 7.26] (n=69) |

Medians: 18.00 candidates, 5.00 ranked, 12.27 s retrieval, 5.45 s ranking; 3.00 queries per claim.

Ranked sources found by: proposition 211, anchor 120, refutation 85 (a source two queries found counts for both).

References found, then cut:

- evidence_retrieval: same domain as a higher-ranked source (pewresearch.org): 2

| By dataset | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| custom | 69 | 67 | 9.0% | 25.4% | 98.6% |

| By language | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| en | 48 | 46 | 10.9% | 23.9% | 97.9% |
| es | 21 | 21 | 4.8% | 28.6% | 100.0% |

## Response time

Seconds per stage over the 69 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 69 | 0.1 | 0.4 | 1.5 | 0.2% |
| Evidence retrieval | 69 | 12.3 | 22.6 | 40.8 | 10.8% |
| Ranking | 69 | 5.5 | 9.8 | 17.6 | 4.8% |
| The model's verdict (with its wait for a permit) | 68 | 112.5 | 177.2 | 259.4 | 84.2% |
| Second look, where taken | 0 | n/a | n/a | n/a | 0.0% |
| Whole claim | 69 | 133.2 | 197.3 | 273.2 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 68 (0) |
| Claims the model was not asked about | 1 |
| Prompt / completion tokens | 131765 / 13300 |
| Tokens per claim asked (prompt / completion) | 1937.7 / 195.6 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 64.359 / 98.574 / 129.982 |
| Claim latency, median / p90 (s) | 133.248 / 197.311 |
| Completion tokens per second | 3.0 |
| Cost | n/a (no price given, or tokens unknown) |
