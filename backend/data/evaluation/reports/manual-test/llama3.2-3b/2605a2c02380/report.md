# manual-test · llama3.2:3b

Run `2605a2c02380` · provider `host.docker.internal:11434` · harness v1 · thresholds `e1bae39fd2a3` · corpus `snapshot` (12 points)

Dataset sha256 `1ea9a8b72ec3`, 70 rows; 70 run, 0 not run. Commits: `4e0e67ff3f1e`

Intervals: percentile 95% bootstrap over claims, 10000 resamples, seed 2026.

## Headline

| Scored claims | All | Without leak flags |
|---|---|---|
| Claims | 70 | 56 |
| Accuracy | 52.9% [41.4%, 64.3%] | 51.8% [39.3%, 64.3%] |
| Macro-F1 (gold classes) | 0.218 [0.168, 0.264] | 0.215 [0.160, 0.267] |
| Coverage (not UNVERIFIED) | 100.0% [100.0%, 100.0%] | 100.0% [100.0%, 100.0%] |
| Selective accuracy | 52.9% [41.4%, 64.3%] | 51.8% [39.3%, 64.3%] |
| Cohen's kappa vs gold | 0.168 [0.002, 0.339] | 0.194 [0.029, 0.367] |

## What was set apart

Never in the error rate: each would measure an outage, not the pipeline.

| Outcome | Claims | Ids |
|---|---|---|
| error | 0 |  |
| searchUnavailable | 0 |  |
| llmUnreachable | 0 |  |
| scored | 70 |  |

| Flag | Flagged | Clear | Undetermined / n.a. | Ids |
|---|---|---|---|---|
| temporalLeak (cited source newer than the claim) | 14 | 30 | 26 | fact013, fact014, fact030, fact031, fact050, fact079, fact080, fact084, fact095, fact119, fact121, fact150, fact167, fact173 |
| verdictLeak (a ranked source is the fact-checker's own site) | 0 | 0 | 70 |  |

Ranked but uncited sources newer than the claim: 7 over 7 claims (counted, not flagged). Invalid model output (scored as UNVERIFIED): 0.

## Per class (all scored claims)

| Class | Precision | Recall | F1 | Support | Predicted |
|---|---|---|---|---|---|
| TRUE | 74.3% | 56.5% | 0.642 | 46 | 35 |
| PARTIALLY_TRUE | 0.0% | 0.0% | 0.000 | 4 | 1 |
| MISLEADING | n/a | 0.0% | 0.000 | 1 | 0 |
| FALSE | 32.4% | 73.3% | 0.449 | 15 | 34 |
| UNVERIFIED | n/a | 0.0% | 0.000 | 4 | 0 |

Macro-F1 averages over the classes with gold support: TRUE, PARTIALLY_TRUE, MISLEADING, FALSE, UNVERIFIED.

## Confusion matrix (gold rows, predicted columns)

| gold \ predicted | TRUE | PARTIALLY_TRUE | MISLEADING | FALSE | UNVERIFIED |
|---|---|---|---|---|---|
| TRUE | 26 | 1 | 0 | 19 | 0 |
| PARTIALLY_TRUE | 1 | 0 | 0 | 3 | 0 |
| MISLEADING | 1 | 0 | 0 | 0 | 0 |
| FALSE | 4 | 0 | 0 | 11 | 0 |
| UNVERIFIED | 3 | 0 | 0 | 1 | 0 |

## By language

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| en | 47 | 51.1% [36.2%, 66.0%] | 0.269 | 100.0% | 51.1% |
| es | 23 | 56.5% [34.8%, 78.3%] | 0.267 | 100.0% | 56.5% |

## By topicGroup

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| culture | 11 | 36.4% [9.1%, 63.6%] | 0.255 | 100.0% | 36.4% |
| environment | 18 | 44.4% [22.2%, 66.7%] | 0.227 | 100.0% | 44.4% |
| health | 16 | 62.5% [37.5%, 87.5%] | 0.344 | 100.0% | 62.5% |
| science | 16 | 62.5% [37.5%, 87.5%] | 0.342 | 100.0% | 62.5% |
| society | 9 | 55.6% [22.2%, 88.9%] | 0.312 | 100.0% | 55.6% |

## By claimType

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| factual | 44 | 56.8% [40.9%, 70.5%] | 0.287 | 100.0% | 56.8% |
| interpretive | 2 | 50.0% [0.0%, 100.0%] | 0.333 | 100.0% | 50.0% |
| numerical | 24 | 45.8% [25.0%, 66.7%] | 0.239 | 100.0% | 45.8% |

## By sourceTier

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| press_release | 3 | 66.7% [0.0%, 100.0%] | 0.556 | 100.0% | 66.7% |
| primary | 37 | 48.6% [32.4%, 64.9%] | 0.183 | 100.0% | 48.6% |
| reference_media | 30 | 56.7% [40.0%, 73.3%] | 0.302 | 100.0% | 56.7% |

## By origin

| Value | n | Accuracy | Macro-F1 | Coverage | Selective acc. |
|---|---|---|---|---|---|
| mutated | 15 | 73.3% [53.3%, 93.3%] | 0.846 | 100.0% | 73.3% |
| natural | 55 | 47.3% [34.5%, 60.0%] | 0.169 | 100.0% | 47.3% |

## Retrieval

70 claims searched (69 with reference links), 0 with search unavailable and 0 errors left out; 0 reference link(s) on the fact-checker's own site removed from the reference set; 0 searched claim(s) have only placeholder references ("<LINK NOT AVAILABLE>" in the set). Means with 95% bootstrap intervals over claims.

| Metric | Value |
|---|---|
| Reference link among candidates | 14.5% [7.2%, 23.2%] (n=69) |
| Reference link among ranked evidence | 8.7% [2.9%, 15.9%] (n=69) |
| Reference link among cited evidence | 5.8% [1.5%, 11.6%] (n=69) |
| Reference domain among candidates | 34.8% [24.6%, 46.4%] (n=69) |
| Reference domain among ranked evidence | 23.2% [13.0%, 33.3%] (n=69) |
| Reference domain among cited evidence | 13.0% [5.8%, 21.7%] (n=69) |
| Link MRR (ranked) | 2.9% [0.9%, 5.4%] (n=69) |
| Domain MRR (ranked) | 11.8% [6.2%, 18.2%] (n=69) |
| Claims with any ranked evidence | 100.0% [100.0%, 100.0%] (n=70) |
| Candidates per claim | 20.93 [19.70, 22.24] (n=70) |
| Ranked sources per claim | 4.87 [4.74, 4.97] (n=70) |
| Share cut at ranking (gate, cap) | 13.0% [8.2%, 18.2%] (n=70) |
| Distinct domains among ranked | 4.84 [4.70, 4.96] (n=70) |
| Ranked from rated domains | 6.4% [4.0%, 9.3%] (n=70) |
| Ranked from the internal corpus | 0.0% [0.0%, 0.0%] (n=70) |
| Fact-checker's own page ranked (x-fact) | n/a (n=0) |
| Retrieval seconds per claim | 16.51 [14.77, 18.42] (n=70) |
| Ranking seconds per claim | 7.29 [6.54, 8.12] (n=70) |

Medians: 21.00 candidates, 5.00 ranked, 14.13 s retrieval, 6.32 s ranking; 3.00 queries per claim.

Ranked sources found by: proposition 180, anchor 125, refutation 57, follow_up 28 (a source two queries found counts for both).

References found, then cut:

- evidence_retrieval: cut by pre-rank funnel (rank 9 of 12, top 5 kept): 1
- evidence_retrieval: same domain as a higher-ranked source (space.com): 1
- evidence_retrieval: cut by pre-rank funnel (rank 9 of 16, top 5 kept): 1
- evidence_retrieval: cut by pre-rank funnel (rank 8 of 15, top 5 kept): 1
- evidence_retrieval: same domain as a higher-ranked source (en.wikipedia.org): 1

| By dataset | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| custom | 70 | 69 | 8.7% | 23.2% | 100.0% |

| By language | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |
|---|---|---|---|---|---|
| en | 47 | 46 | 10.9% | 26.1% | 100.0% |
| es | 23 | 23 | 4.3% | 17.4% | 100.0% |

## Response time

Seconds per stage over the 70 scored claims, from the pipeline's own events. The model's span includes waiting for the LLM permit; the call latency under Cost is the answer time alone. A response time compares only between runs made alone on the machine.

| Stage | Claims | Median | p90 | Max | Share of the time |
|---|---|---|---|---|---|
| Entities of the claim | 70 | 0.1 | 0.2 | 3.8 | 0.1% |
| Evidence retrieval | 70 | 14.1 | 28.6 | 40.6 | 8.8% |
| Ranking | 70 | 6.3 | 12.6 | 18.2 | 3.9% |
| The model's verdict (with its wait for a permit) | 70 | 120.4 | 197.2 | 367.3 | 70.5% |
| Second look, where taken | 17 | 117.8 | 165.6 | 208.4 | 16.7% |
| Whole claim | 70 | 150.8 | 300.4 | 400.4 |  |

## Cost, latency and tokens

|  | Value |
|---|---|
| LLM calls (failed) | 106 (2) |
| Claims the model was not asked about | 0 |
| Prompt / completion tokens | 178077 / 17667 |
| Tokens per claim asked (prompt / completion) | 2544.0 / 252.4 |
| Calls with no usage reported | 0 |
| LLM call latency, median / p90 / max (s) | 59.266 / 91.503 / 173.554 |
| Claim latency, median / p90 (s) | 150.798 / 300.380 |
| Completion tokens per second | 2.8 |
| Cost | n/a (no price given, or tokens unknown) |
